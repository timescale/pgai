import asyncio
import datetime
import logging
import os
import signal
import sys
from collections.abc import Sequence
from typing import Any

import click
import structlog
from ddtrace import tracer
from dotenv import load_dotenv
from pytimeparse import parse  # type: ignore

from .__init__ import __version__

load_dotenv()

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
log = structlog.get_logger()


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


@click.command(name="download-models")
def download_models():
    import docling.utils.model_downloader

    from .vectorizer.parsing import DOCLING_CACHE_DIR

    docling.utils.model_downloader.download_models(
        progress=True,
        output_dir=DOCLING_CACHE_DIR,  # pyright: ignore [reportUndefinedVariable]
    )


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
    help="The interval, in duration string or integer (seconds), "
    "to wait before checking for new work after processing "
    "all available work in the queue.",
    # noqa
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
    "-c",
    "--concurrency",
    type=click.IntRange(1),
    default=None,
    show_default=True,
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
    log_level: str,
    poll_interval: int,
    once: bool,
    concurrency: int | None,
    exit_on_error: bool | None,
) -> None:
    asyncio.run(
        async_run_vectorizer_worker(
            db_url,
            vectorizer_ids,
            log_level,
            poll_interval,
            once,
            concurrency,
            exit_on_error,
        )
    )


async def async_run_vectorizer_worker(
    db_url: str,
    vectorizer_ids: Sequence[int],
    log_level: str,
    poll_interval: int,
    once: bool,
    concurrency: int | None,
    exit_on_error: bool | None,
) -> None:
    from .vectorizer import Worker

    # gracefully handle being asked to shut down
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(get_log_level(log_level))
    )

    worker = Worker(
        db_url,
        datetime.timedelta(seconds=poll_interval),
        once,
        vectorizer_ids,
        exit_on_error,
        concurrency,
    )
    exception = await worker.run()
    if exception is not None:
        sys.exit(1)


@click.group()
@click.version_option(version=__version__)
def vectorizer():
    pass


@click.group()
@click.version_option(version=__version__)
def cli():
    pass


vectorizer.add_command(vectorizer_worker)
vectorizer.add_command(download_models)
cli.add_command(vectorizer)


@cli.command()
@click.option(
    "-d",
    "--db-url",
    type=click.STRING,
    default="postgres://postgres@localhost:5432/postgres",
    show_default=True,
    help="The database URL to connect to",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    show_default=True,
    help="Raise an error when the extension already exists and is at the latest version.",  # noqa: E501
)
def install(db_url: str, strict: bool) -> None:
    import pgai

    pgai.install(db_url, strict=strict)
