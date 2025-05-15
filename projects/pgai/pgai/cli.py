import asyncio
import datetime
import logging
import os
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import click
import psycopg
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
    log.info(f"pgai {__version__} installed")


@click.group(name="semantic-catalog")
@click.version_option(version=__version__)
def semantic_catalog():
    pass


@semantic_catalog.command()
@click.option(
    "-d",
    "--db-url",
    type=click.STRING,
    default="postgres://postgres@localhost:5432/postgres",
    show_default=True,
    help="The connection URL to the database to find objects in.",
)
@click.option(
    "-m",
    "--model",
    type=click.STRING,
    default="anthropic:claude-3-7-sonnet-latest",
    show_default=True,
    help="The LLM model to generate descriptions",
)
@click.option(
    "-c",
    "--catalog-name",
    type=click.STRING,
    default="default",
    show_default=True,
    help="The name of the semantic catalog to insert descriptions into",
)
@click.option(
    "--include-schema",
    type=click.STRING,
    default=None,
    help="A regular expression to match against schema names to be included in output.",
)
@click.option(
    "--exclude-schema",
    type=click.STRING,
    default=None,
    help="A regular expression to match against schema names to be excluded from output.",  # noqa: E501
)
@click.option(
    "--include-table",
    type=click.STRING,
    default=None,
    help="A regular expression to match against table names to be included in output.",
)
@click.option(
    "--exclude-table",
    type=click.STRING,
    default=None,
    help="A regular expression to match against table names to be excluded from output.",  # noqa: E501
)
@click.option(
    "--include-view",
    type=click.STRING,
    default=None,
    help="A regular expression to match against view names to be included in output.",
)
@click.option(
    "--exclude-view",
    type=click.STRING,
    default=None,
    help="A regular expression to match against view names to be excluded from output.",
)
@click.option(
    "--include-proc",
    type=click.STRING,
    default=None,
    help="A regular expression to match against procedure/function names to be included in output.",  # noqa: E501
)
@click.option(
    "--exclude-proc",
    type=click.STRING,
    default=None,
    help="A regular expression to match against proc names to be excluded from output.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(
        exists=False, dir_okay=False, writable=True, resolve_path=True, path_type=Path
    ),
    default=None,
    help="The path to a file to write output to.",
)
@click.option(
    "-a",
    "--append",
    type=click.BOOL,
    default=False,
    help="Append to the output file instead of overwriting it.",
)
@click.option(
    "-f",
    "--format",
    type=click.Choice(["semantic-catalog", "comment"], case_sensitive=False),
    default="semantic-catalog",
    help="Output format (sql, comment)",
)
def build(
    db_url: str,
    model: str,
    catalog_name: str,
    include_schema: str | None = None,
    exclude_schema: str | None = None,
    include_table: str | None = None,
    exclude_table: str | None = None,
    include_view: str | None = None,
    exclude_view: str | None = None,
    include_proc: str | None = None,
    exclude_proc: str | None = None,
    output: Path | None = None,
    append: bool = False,
    format: Literal["semantic-catalog", "comment"] = "semantic-catalog",
) -> None:
    from pgai.semantic_catalog.builder import build

    # TODO: add progress feedback with Rich and add --quiet to turn it off
    # TODO: is async io for stdout/file needed?
    with sys.stdout if not output else output.open(mode="a" if append else "w") as f:
        asyncio.run(
            build(
                db_url,
                model,  # pyright: ignore [reportArgumentType]
                catalog_name,
                output=f,
                include_schema=include_schema,
                exclude_schema=exclude_schema,
                include_table=include_table,
                exclude_table=exclude_table,
                include_view=include_view,
                exclude_view=exclude_view,
                include_proc=include_proc,
                exclude_proc=exclude_proc,
                format=format,
            )
        )


@semantic_catalog.command()
@click.argument("catalog-name")
@click.option(
    "-d",
    "--db-url",
    type=click.STRING,
    default="postgres://postgres@localhost:5432/postgres",
    show_default=True,
    help="The connection URL to the database the semantic catalog is in.",
)
@click.option(
    "-c",
    "--embed-config",
    type=click.STRING,
    default=None,
    help="The name of the embedding configuration to generate vector for. (If None, do all)",  # noqa: E501
)
@click.option(
    "-b",
    "--batch-size",
    type=click.INT,
    default=None,
    help="The number of embeddings to generate per batch.",
)
def vectorize(
    catalog_name: str,
    db_url: str,
    embed_config: str | None,
    batch_size: int | None = None,
) -> None:
    batch_size = batch_size if batch_size is not None else 32

    async def do():
        from pgai.semantic_catalog import from_name

        async with await psycopg.AsyncConnection.connect(db_url) as con:
            sc = await from_name(con, catalog_name)
            match embed_config:
                case None:
                    await sc.vectorize_all(con, batch_size=batch_size)
                case _:
                    config = await sc.get_embedding_config(con, embed_config)
                    if config is None:
                        raise ValueError(
                            f"No embedding configuration found for {catalog_name}"
                        )
                    await sc.vectorize(con, embed_config, config, batch_size=batch_size)

    asyncio.run(do())


cli.add_command(semantic_catalog)
