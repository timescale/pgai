import asyncio
import datetime
import logging
import os
import random
import sys
import time
from collections.abc import Sequence

import click
import psycopg
import structlog
from dotenv import load_dotenv
from psycopg.rows import dict_row, namedtuple_row
from pytimeparse import parse  # type: ignore

from .__init__ import __version__
from .vectorizer.vectorizer import Vectorizer, Worker

load_dotenv()

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
log = structlog.get_logger()


def get_pgai_version(cur: psycopg.Cursor) -> str | None:
    cur.execute("select extversion from pg_catalog.pg_extension where extname = 'ai'")
    row = cur.fetchone()
    return row[0] if row is not None else None


def get_vectorizer_ids(
    cur: psycopg.Cursor, vectorizer_ids: Sequence[int] | None = None
) -> list[int]:
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


def get_vectorizer(db_url: str, vectorizer_id: int) -> Vectorizer | None:
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
            log.warning("vectorizer not found", vectorizer_id=vectorizer_id)
            return None
        vectorizer = row["vectorizer"]
        embedding = vectorizer["config"]["embedding"]
        api_key_name = embedding["api_key_name"]
        api_key = os.getenv(api_key_name, None)
        if api_key is None:
            log.error(
                "API key not found",
                api_key_name=api_key_name,
                vectorizer_id=vectorizer_id,
            )
            return None
        secrets: dict[str, str | None] = {api_key_name: api_key}
        vectorizer = Vectorizer(**vectorizer)
        vectorizer.config.embedding.set_api_key(secrets)
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


@click.command()
@click.version_option(version=__version__)
@click.option(
    "-d",
    "--db-url",
    type=click.STRING,
    envvar="VECTORIZER_DB_URL",
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
    default=None,
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
    default=False,
    show_default=True,
    help="Exit after processing all available work.",
)
def run(
    db_url: str,
    vectorizer_ids: Sequence[int] | None,
    concurrency: int,
    log_level: str,
    poll_interval: int,
    once: bool,
) -> None:
    log_level_: int = logging.getLevelNamesMapping()[log_level.upper()]
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(log_level_))
    poll_interval_str = datetime.timedelta(seconds=poll_interval)

    with (
        psycopg.Connection.connect(db_url) as con,
        con.cursor(row_factory=namedtuple_row) as cur,
    ):
        pgai_version = get_pgai_version(cur)
        if pgai_version is None:
            log.critical("the pgai extension is not installed")
            sys.exit(1)
        vectorizer_ids = get_vectorizer_ids(cur, vectorizer_ids)
    if len(vectorizer_ids) == 0:
        log.warning("no vectorizers found")
        return

    while True:
        for vectorizer_id in vectorizer_ids:
            vectorizer = get_vectorizer(db_url, vectorizer_id)
            if vectorizer is None:
                continue
            log.info("running vectorizer", vectorizer_id=vectorizer_id)
            run_vectorizer(db_url, vectorizer, concurrency)
        if once:
            return
        time.sleep(poll_interval)
        log.info(f"sleeping for {poll_interval_str} before polling for new work")
