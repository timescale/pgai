import asyncio
import datetime
import logging
import os
import random
import signal
import sys
import time
import traceback
from collections.abc import Sequence
from typing import Any

import click
import psycopg
import structlog
from ddtrace import tracer
from dotenv import load_dotenv
from psycopg.rows import dict_row, namedtuple_row
from pytimeparse import parse  # type: ignore

from .__init__ import __version__
from .vectorizer.vectorizer import Vectorizer, Worker

load_dotenv()

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
log = structlog.get_logger()


class VectorizerNotFoundError(Exception):
    pass


class ApiKeyNotFoundError(Exception):
    pass


def asbool(value: str | None):
    """Convert the given String to a boolean object.

    Accepted values are `True` and `1`.
    """
    if value is None:
        return False

    return value.lower() in ("true", "1")


def get_bool_env(name: str | None) -> bool:
    if name is None:
        return False

    return asbool(os.getenv(name))


tracer.enabled = get_bool_env("DD_TRACE_ENABLED")


def get_pgai_version(cur: psycopg.Cursor) -> str | None:
    cur.execute("select extversion from pg_catalog.pg_extension where extname = 'ai'")
    row = cur.fetchone()
    return row[0] if row is not None else None


def get_vectorizer_ids(
    db_url: str, vectorizer_ids: Sequence[int] | None = None
) -> list[int]:
    with (
        psycopg.Connection.connect(db_url) as con,
        con.cursor(row_factory=namedtuple_row) as cur,
    ):
        valid_vectorizer_ids: list[int] = []
        if vectorizer_ids is None or len(vectorizer_ids) == 0:
            cur.execute("select id from ai.vectorizer")
        else:
            cur.execute(
                "select id from ai.vectorizer where id = any(%s)",
                [
                    list(vectorizer_ids),
                ],
            )
        for row in cur.fetchall():
            valid_vectorizer_ids.append(row[0])
        random.shuffle(valid_vectorizer_ids)
        return valid_vectorizer_ids


def get_vectorizer(db_url: str, vectorizer_id: int) -> Vectorizer:
    with (
        psycopg.Connection.connect(db_url) as con,
        con.cursor(row_factory=dict_row) as cur,
    ):
        cur.execute(
            "select pg_catalog.to_jsonb(v) as vectorizer from ai.vectorizer v where v.id = %s",  # noqa
            (vectorizer_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise VectorizerNotFoundError(f"vectorizer_id={vectorizer_id}")
        vectorizer = row["vectorizer"]
        embedding = vectorizer["config"]["embedding"]
        vectorizer = Vectorizer(**vectorizer)
        # The Ollama API doesn't need a key, so `api_key_name` may be unset
        if "api_key_name" in embedding:
            api_key_name = embedding["api_key_name"]
            api_key = os.getenv(api_key_name, None)
            if api_key is not None:
                log.debug(f"obtained secret '{api_key_name}' from environment")
            else:
                cur.execute(
                    "select ai.reveal_secret(%s)",
                    (api_key_name,),
                )
                row = cur.fetchone()
                api_key = row["reveal_secret"] if row is not None else None
                if api_key is not None:
                    log.debug(f"obtained secret '{api_key_name}' from database")
            if not api_key:
                raise ApiKeyNotFoundError(
                    f"api_key_name={api_key_name} vectorizer_id={vectorizer_id}"
                )
            secrets: dict[str, str | None] = {api_key_name: api_key}
            # The Ollama API doesn't need a key, so doesn't support `set_api_key`
            set_api_key = getattr(vectorizer.config.embedding, "set_api_key", None)
            if callable(set_api_key):
                set_api_key(secrets)
            else:
                log.error(
                    f"cannot set secret value '{api_key_name}' for vectorizer with id: '{vectorizer.id}'"  # noqa
                )
        return vectorizer


def run_vectorizer(db_url: str, vectorizer: Vectorizer, concurrency: int) -> None:
    async def run_workers(
        db_url: str, vectorizer: Vectorizer, concurrency: int
    ) -> list[int]:
        tasks = [
            asyncio.create_task(Worker(db_url, vectorizer).run())
            for _ in range(concurrency)
        ]
        return await asyncio.gather(*tasks)

    results = asyncio.run(run_workers(db_url, vectorizer, concurrency))
    items = sum(results)
    log.info("finished processing vectorizer", items=items, vectorizer_id=vectorizer.id)


class TimeDurationParamType(click.ParamType):
    name = "time duration"

    def convert(self, value, param, ctx) -> int:  # type: ignore
        val: int | None = parse(value)  # type: ignore
        if val is not None:
            return val  # type: ignore
        try:
            val = int(value, 10)
            if val < 0:
                self.fail(
                    "time duration can't be negative",
                    param,
                    ctx,
                )
            return val
        except ValueError:
            self.fail(
                f"{value!r} is not a valid duration string or integer",
                param,
                ctx,
            )


def get_log_level(level: str) -> int:
    level_upper = level.upper()
    # We are targeting python 3.10 that's why we need to use getLevelName which
    # is deprecated, but still there for backwards compatibility.
    level_name = logging.getLevelName(level_upper)  # type: ignore
    if level_upper != "INFO" and isinstance(level_name, int):
        return level_name
    return logging.getLevelName("INFO")  # type: ignore


def shutdown_handler(signum: int, _frame: Any):
    signame = signal.Signals(signum).name
    log.info(f"received {signame}, exiting")
    exit(0)


@click.command(name="worker")
@click.version_option(version=__version__)
@click.option(
    "-d",
    "--db-url",
    type=click.STRING,
    default="postgres://postgres@localhost:5432/postgres",
    show_default=True,
    help="The database URL to connect to",
)
@click.option(
    "-i",
    "--vectorizer-id",
    "vectorizer_ids",
    type=click.INT,
    multiple=True,
    help="Only fetch work from the given vectorizer ids. If not provided, all vectorizers will be fetched.",  # noqa
    default=[],
)
@click.option(
    "-c",
    "--concurrency",
    type=click.IntRange(1),
    default=1,
    show_default=True,
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARN", "ERROR", "FATAL", "CRITICAL"], case_sensitive=False
    ),
    default="INFO",
)
@click.option(
    "--poll-interval",
    type=TimeDurationParamType(),
    default="5m",
    show_default=True,
    help="The interval, in duration string or integer (seconds), to wait before checking for new work after processing all available work in the queue.",  # noqa
)
@click.option(
    "--once",
    type=click.BOOL,
    is_flag=True,
    default=False,
    show_default=True,
    help="Exit after processing all available work (implies --exit-on-error).",
)
@click.option(
    "--exit-on-error",
    type=click.BOOL,
    default=None,
    show_default=True,
    help="Exit immediately when an error occurs.",
)
def vectorizer_worker(
    db_url: str,
    vectorizer_ids: Sequence[int],
    concurrency: int,
    log_level: str,
    poll_interval: int,
    once: bool,
    exit_on_error: bool | None,
) -> None:
    # gracefully handle being asked to shut down
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(get_log_level(log_level))
    )
    log.debug("starting vectorizer worker")
    poll_interval_str = datetime.timedelta(seconds=poll_interval)

    dynamic_mode = len(vectorizer_ids) == 0
    valid_vectorizer_ids = []

    can_connect = False
    pgai_version = None
    if once and exit_on_error is None:
        # --once implies --exit-on-error
        exit_on_error = True

    while True:
        try:
            if not can_connect or pgai_version is None:
                with (
                    psycopg.Connection.connect(db_url) as con,
                    con.cursor(row_factory=namedtuple_row) as cur,
                ):
                    pgai_version = get_pgai_version(cur)
                    can_connect = True
                    if pgai_version is None:
                        log.error("the pgai extension is not installed")
                        if exit_on_error:
                            sys.exit(1)

            if can_connect and pgai_version is not None:
                if not dynamic_mode and len(valid_vectorizer_ids) != len(
                    vectorizer_ids
                ):
                    valid_vectorizer_ids = get_vectorizer_ids(db_url, vectorizer_ids)
                    if len(valid_vectorizer_ids) != len(vectorizer_ids):
                        log.error(
                            f"invalid vectorizers, wanted: {list(vectorizer_ids)}, got: {valid_vectorizer_ids}"  # noqa: E501 (line too long)
                        )
                        if exit_on_error:
                            sys.exit(1)
                else:
                    valid_vectorizer_ids = get_vectorizer_ids(db_url, vectorizer_ids)
                    if len(valid_vectorizer_ids) == 0:
                        log.warning("no vectorizers found")

                for vectorizer_id in valid_vectorizer_ids:
                    try:
                        vectorizer = get_vectorizer(db_url, vectorizer_id)
                        log.info("running vectorizer", vectorizer_id=vectorizer_id)
                        run_vectorizer(db_url, vectorizer, concurrency)
                    except (VectorizerNotFoundError, ApiKeyNotFoundError) as e:
                        log.error(
                            f"error getting vectorizer: {type(e).__name__}: {str(e)} "
                        )
                        if exit_on_error:
                            sys.exit(1)
        except psycopg.OperationalError as e:
            if "connection failed" in str(e):
                log.error(f"unable to connect to database: {str(e)}")
            else:
                log.error(f"unexpected error: {str(e)}")
            if exit_on_error:
                sys.exit(1)
        except Exception as e:
            # catch any exceptions, log them, and keep on going
            log.error(f"unexpected error: {str(e)}")
            for exception_line in traceback.format_exception(e):
                for line in exception_line.rstrip().split("\n"):
                    log.debug(line)
            if exit_on_error:
                sys.exit(1)

        if once:
            return
        log.info(f"sleeping for {poll_interval_str} before polling for new work")
        time.sleep(poll_interval)


@click.group()
@click.version_option(version=__version__)
def vectorizer():
    pass


@click.group()
@click.version_option(version=__version__)
def cli():
    pass


vectorizer.add_command(vectorizer_worker)
cli.add_command(vectorizer)
