import asyncio
import datetime
import logging
import os
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

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
    envvar="TARGET_DB",
)
@click.option(
    "-m",
    "--model",
    type=click.STRING,
    default="openai:o3",
    show_default=True,
    help="The LLM model to generate descriptions",
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
    type=click.Path(exists=False, dir_okay=False, writable=True, path_type=Path),
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
    "-s",
    "--sample-size",
    type=click.INT,
    default=3,
    help="Number of sample rows to include in the context",
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Do not print progress messages.",
)
@click.option(
    "-l",
    "--log-file",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="The path to a file to write log messages to.",
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARN", "ERROR", "FATAL", "CRITICAL"], case_sensitive=False
    ),
    default="INFO",
)
def describe(
    db_url: str,
    model: str,
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
    sample_size: int = 3,
    quiet: bool = False,
    log_file: Path | None = None,
    log_level: str | None = "INFO",
) -> None:
    if log_file:
        import logging

        logging.basicConfig(
            level=get_log_level(log_level or "INFO"),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file.expanduser().resolve()),
            ],
        )

    from rich.console import Console

    from pgai.semantic_catalog.describe import describe

    output = output.expanduser().resolve() if output else None

    with sys.stdout if not output else output.open(mode="a" if append else "w") as f:
        asyncio.run(
            describe(
                db_url,
                model,  # pyright: ignore [reportArgumentType]
                output=f,
                console=Console(stderr=True, quiet=quiet),
                include_schema=include_schema,
                exclude_schema=exclude_schema,
                include_table=include_table,
                exclude_table=exclude_table,
                include_view=include_view,
                exclude_view=exclude_view,
                include_proc=include_proc,
                exclude_proc=exclude_proc,
                sample_size=sample_size,
            )
        )


@semantic_catalog.command()
@click.option(
    "-d",
    "--db-url",
    type=click.STRING,
    default="postgres://postgres@localhost:5432/postgres",
    show_default=True,
    help="The connection URL to the database the semantic catalog is in.",
    envvar="CATALOG_DB",
)
@click.option(
    "-n",
    "--catalog-name",
    type=click.STRING,
    default="default",
    help="The name of the semantic catalog to generate embeddings for.",  # noqa: E501
)
@click.option(
    "-e",
    "--embed-config",
    type=click.STRING,
    default=None,
    help="The name of the embedding configuration to generate embeddings for. (If None, do all)",  # noqa: E501
)
@click.option(
    "-b",
    "--batch-size",
    type=click.INT,
    default=None,
    help="The number of embeddings to generate per batch.",
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Do not print log messages.",
)
@click.option(
    "-l",
    "--log-file",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="The path to a file to write log messages to.",
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARN", "ERROR", "FATAL", "CRITICAL"], case_sensitive=False
    ),
    default="INFO",
)
def vectorize(
    db_url: str,
    catalog_name: str | None,
    embed_config: str | None,
    batch_size: int | None = None,
    quiet: bool = False,
    log_file: Path | None = None,
    log_level: str | None = "INFO",
) -> None:
    import logging

    log_handlers: list[logging.Handler] = []
    if log_file:
        log_handlers.append(logging.FileHandler(log_file.expanduser().resolve()))
    if not quiet:
        from rich.console import Console
        from rich.logging import RichHandler

        log_handlers.append(
            RichHandler(console=Console(stderr=True), rich_tracebacks=True)
        )

    if len(log_handlers) > 0:
        logging.basicConfig(
            level=get_log_level(log_level or "INFO"),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=log_handlers,
        )

    catalog_name = catalog_name or "default"
    batch_size = batch_size if batch_size is not None else 32

    async def do():
        from pgai.semantic_catalog import from_name

        async with await psycopg.AsyncConnection.connect(db_url) as con:
            sc = await from_name(con, catalog_name)
            match embed_config:
                case None:
                    await sc.vectorize_all(con, batch_size=batch_size)
                case _:
                    config = await sc.get_embedding(con, embed_config)
                    if config is None:
                        raise ValueError(
                            f"No embedding configuration found for {catalog_name}"
                        )
                    await sc.vectorize(con, embed_config, config, batch_size=batch_size)

    asyncio.run(do())


@semantic_catalog.command()
@click.option(
    "-d",
    "--db-url",
    type=click.STRING,
    default="postgres://postgres@localhost:5432/postgres",
    show_default=True,
    help="The connection URL to the database the semantic catalog is in.",
    envvar="CATALOG_DB",
)
@click.option(
    "-p",
    "--provider",
    type=click.STRING,
    default="openai",
    help="The name of the embedding provider.",
)
@click.option(
    "-m",
    "--model",
    type=click.STRING,
    default="text-embedding-3-small",
    help="The name of the embedding model.",
)
@click.option(
    "-v",
    "--vector-dimensions",
    type=click.INT,
    default=1536,
    help="The number of dimensions in the embeddings.",
)
@click.option(
    "-n",
    "--catalog-name",
    type=click.STRING,
    default="default",
    help="The name of the semantic catalog to generate embeddings for.",
)
@click.option(
    "-e",
    "--embed-config",
    type=click.STRING,
    default=None,
    help="The name of the embedding configuration to generate embeddings for. (If None, do all)",  # noqa: E501
)
@click.option(
    "--base-url",
    type=click.STRING,
    default=None,
    help="The base_url for the embedding provider",
)
@click.option(
    "--api-key-name",
    type=click.STRING,
    default=None,
    help="The name of the environment variable containing the API key for the embedding provider",  # noqa: E501
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Do not print log messages.",
)
@click.option(
    "-l",
    "--log-file",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="The path to a file to write log messages to.",
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARN", "ERROR", "FATAL", "CRITICAL"], case_sensitive=False
    ),
    default="INFO",
)
def create(
    db_url: str,
    provider: str,
    model: str,
    vector_dimensions: int,
    catalog_name: str | None = None,
    embed_config: str | None = None,
    base_url: str | None = None,
    api_key_name: str | None = None,
    quiet: bool = False,
    log_file: Path | None = None,
    log_level: str | None = "INFO",
):
    import logging

    log_handlers: list[logging.Handler] = []
    if log_file:
        log_handlers.append(logging.FileHandler(log_file.expanduser().resolve()))
    if not quiet:
        from rich.console import Console
        from rich.logging import RichHandler

        log_handlers.append(
            RichHandler(console=Console(stderr=True), rich_tracebacks=True)
        )

    if len(log_handlers) > 0:
        logging.basicConfig(
            level=get_log_level(log_level or "INFO"),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=log_handlers,
        )

    from pgai.semantic_catalog.vectorizer import (
        OllamaConfig,
        OpenAIConfig,
        SentenceTransformersConfig,
    )

    match provider.lower():
        case "sentence_transformers":
            config = SentenceTransformersConfig.create(
                model=str(model),
                dimensions=int(vector_dimensions),
            )
        case "openai":
            config = OpenAIConfig.create(
                model=str(model),
                dimensions=int(vector_dimensions),
                base_url=base_url,
                api_key_name=api_key_name,
            )
        case "ollama":
            config = OllamaConfig.create(
                model=str(model),
                dimensions=int(vector_dimensions),
                base_url=base_url,
            )
        case _:
            raise RuntimeError(f"unrecognized provider {provider}")
    assert config is not None

    import pgai

    pgai.install(db_url, strict=False)

    async def do():
        from pgai.semantic_catalog import create

        async with await psycopg.AsyncConnection.connect(db_url) as con:
            sc = await create(
                con, catalog_name, embedding_name=embed_config, embedding_config=config
            )
            print(f"""created "{sc.name}" semantic catalog with id: {sc.id}""")

    asyncio.run(do())


@semantic_catalog.command(name="import")
@click.option(
    "-d",
    "--db-url",
    type=click.STRING,
    default="postgres://postgres@localhost:5432/postgres",
    show_default=True,
    help="The connection URL to the database the database to generate sql for.",
    envvar="TARGET_DB",
)
@click.option(
    "-c",
    "--catalog-db-url",
    type=click.STRING,
    default="postgres://postgres@localhost:5432/postgres",
    show_default=True,
    help="The connection URL to the database the semantic catalog is in.",
    envvar="CATALOG_DB",
)
@click.option(
    "-f",
    "--yaml-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="The path to a yaml file.",
)
@click.option(
    "-n",
    "--catalog-name",
    type=click.STRING,
    default="default",
    help="The name of the semantic catalog to generate embeddings for.",  # noqa: E501
)
@click.option(
    "-e",
    "--embed-config",
    type=click.STRING,
    default=None,
    help="The name of the embedding configuration to generate embeddings for. (If None, do all)",  # noqa: E501
)
@click.option(
    "-b",
    "--batch-size",
    type=click.INT,
    default=None,
    help="The number of embeddings to generate per batch.",
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Do not print log messages.",
)
@click.option(
    "-l",
    "--log-file",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="The path to a file to write log messages to.",
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARN", "ERROR", "FATAL", "CRITICAL"], case_sensitive=False
    ),
    default="INFO",
)
def import_catalog(
    db_url: str,
    catalog_db_url: str,
    yaml_file: Path,
    catalog_name: str | None,
    embed_config: str | None,
    batch_size: int | None = None,
    quiet: bool = False,
    log_file: Path | None = None,
    log_level: str | None = "INFO",
) -> None:
    import logging

    log_handlers: list[logging.Handler] = []
    if log_file:
        log_handlers.append(logging.FileHandler(log_file.expanduser().resolve()))
    if not quiet:
        from rich.console import Console
        from rich.logging import RichHandler

        log_handlers.append(
            RichHandler(console=Console(stderr=True), rich_tracebacks=True)
        )

    if len(log_handlers) > 0:
        logging.basicConfig(
            level=get_log_level(log_level or "INFO"),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=log_handlers,
        )

    from rich.console import Console

    console = Console(stderr=True, quiet=quiet)

    catalog_name = catalog_name or "default"
    yaml_file = yaml_file.expanduser().resolve()
    assert yaml_file.is_file(), "invalid yaml file"

    async def do():
        from pgai.semantic_catalog import from_name

        async with (
            await psycopg.AsyncConnection.connect(catalog_db_url) as ccon,
            await psycopg.AsyncConnection.connect(db_url) as tcon,
        ):
            console.status(f"finding '{catalog_name}' catalog...")
            sc = await from_name(ccon, catalog_name)
            with yaml_file.open(mode="r") as r:
                await sc.import_catalog(
                    ccon, tcon, r, embed_config, batch_size, console
                )

    asyncio.run(do())


@semantic_catalog.command(name="export")
@click.option(
    "-c",
    "--catalog-db-url",
    type=click.STRING,
    default="postgres://postgres@localhost:5432/postgres",
    show_default=True,
    help="The connection URL to the database the semantic catalog is in.",
    envvar="CATALOG_DB",
)
@click.option(
    "-f",
    "--yaml-file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="The path to a yaml file.",
)
@click.option(
    "-n",
    "--catalog-name",
    type=click.STRING,
    default="default",
    help="The name of the semantic catalog to generate embeddings for.",  # noqa: E501
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Do not print log messages.",
)
@click.option(
    "-l",
    "--log-file",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="The path to a file to write log messages to.",
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARN", "ERROR", "FATAL", "CRITICAL"], case_sensitive=False
    ),
    default="INFO",
)
def export_catalog(
    catalog_db_url: str,
    yaml_file: Path,
    catalog_name: str | None,
    quiet: bool = False,
    log_file: Path | None = None,
    log_level: str | None = "INFO",
) -> None:
    import logging

    log_handlers: list[logging.Handler] = []
    if log_file:
        log_handlers.append(logging.FileHandler(log_file.expanduser().resolve()))
    if not quiet:
        from rich.console import Console
        from rich.logging import RichHandler

        log_handlers.append(
            RichHandler(console=Console(stderr=True), rich_tracebacks=True)
        )

    if len(log_handlers) > 0:
        logging.basicConfig(
            level=get_log_level(log_level or "INFO"),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=log_handlers,
        )

    from rich.console import Console

    console = Console(stderr=True, quiet=quiet)

    catalog_name = catalog_name or "default"
    yaml_file = yaml_file.expanduser().resolve()

    async def do():
        from pgai.semantic_catalog import from_name

        async with await psycopg.AsyncConnection.connect(catalog_db_url) as ccon:
            console.status(f"finding '{catalog_name}' catalog...")
            sc = await from_name(ccon, catalog_name)
            console.status("exporting semantic catalog to file...")
            with yaml_file.open(mode="w") as w:
                await sc.export_catalog(ccon, w)

    asyncio.run(do())


@semantic_catalog.command()
@click.option(
    "-d",
    "--db-url",
    type=click.STRING,
    default="postgres://postgres@localhost:5432/postgres",
    show_default=True,
    help="The connection URL to the database the database to generate sql for.",
    envvar="TARGET_DB",
)
@click.option(
    "-c",
    "--catalog-db-url",
    type=click.STRING,
    default="postgres://postgres@localhost:5432/postgres",
    show_default=True,
    help="The connection URL to the database the semantic catalog is in.",
    envvar="CATALOG_DB",
)
@click.option(
    "-m",
    "--model",
    type=click.STRING,
    default="anthropic:claude-3-7-sonnet-latest",
    show_default=True,
    help="The LLM model",
)
@click.option(
    "-n",
    "--catalog-name",
    type=click.STRING,
    default="default",
    help="The name of the semantic catalog to use.",
)
@click.option(
    "-e",
    "--embed-config",
    type=click.STRING,
    default=None,
    help="The name of the embedding configuration to use",
)
@click.option(
    "-p",
    "--prompt",
    type=click.STRING,
    default=None,
    help="The question to be answered by the generated SQL statement",
)
@click.option(
    "-s",
    "--sample-size",
    type=click.INT,
    default=3,
    help="Number of sample rows to include in the context",
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Do not print log messages.",
)
@click.option(
    "-l",
    "--log-file",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="The path to a file to write log messages to.",
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARN", "ERROR", "FATAL", "CRITICAL"], case_sensitive=False
    ),
    default="INFO",
)
@click.option(
    "--print-messages",
    is_flag=True,
    help="Print LLM messages.",
)
@click.option(
    "--print-usage",
    is_flag=True,
    help="Print LLM usage metrics.",
)
@click.option(
    "--save-final-prompt",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="The path to a file to write the final prompt to.",
)
def generate_sql(
    db_url: str,
    catalog_db_url: str | None,
    model: str,
    catalog_name: str | None,
    embed_config: str | None,
    prompt: str,
    sample_size: int = 3,
    quiet: bool = False,
    log_file: Path | None = None,
    log_level: str | None = "INFO",
    print_messages: bool = False,
    print_usage: bool = False,
    save_final_prompt: Path | None = None,
) -> None:
    import logging

    log_handlers: list[logging.Handler] = []
    if log_file:
        log_handlers.append(logging.FileHandler(log_file.expanduser().resolve()))
    if not quiet:
        from rich.console import Console
        from rich.logging import RichHandler

        log_handlers.append(
            RichHandler(console=Console(stderr=True), rich_tracebacks=True)
        )

    if len(log_handlers) > 0:
        logging.basicConfig(
            level=get_log_level(log_level or "INFO"),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=log_handlers,
        )

    catalog_db_url = catalog_db_url or db_url
    catalog_name = catalog_name or "default"
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.usage import UsageLimits

    from pgai.semantic_catalog import from_name
    from pgai.semantic_catalog.gen_sql import GenerateSQLResponse

    async def do() -> GenerateSQLResponse:
        if catalog_db_url:
            async with (
                await psycopg.AsyncConnection.connect(db_url) as tcon,
                await psycopg.AsyncConnection.connect(catalog_db_url) as ccon,
            ):
                sc = await from_name(ccon, catalog_name)
                return await sc.generate_sql(
                    ccon,
                    tcon,
                    model=model,  # pyright: ignore [reportArgumentType]
                    prompt=prompt,  # pyright: ignore [reportArgumentType]
                    usage_limits=UsageLimits(),
                    model_settings=ModelSettings(),
                    embedding_name=embed_config,
                    sample_size=sample_size,
                )
        else:
            async with await psycopg.AsyncConnection.connect(db_url) as con:
                sc = await from_name(con, catalog_name)
                return await sc.generate_sql(
                    con,
                    con,
                    model=model,  # pyright: ignore [reportArgumentType]
                    prompt=prompt,  # pyright: ignore [reportArgumentType]
                    usage_limits=UsageLimits(),
                    model_settings=ModelSettings(),
                    embedding_name=embed_config,
                    sample_size=sample_size,
                )

    resp = asyncio.run(do())
    if quiet:
        print(resp.sql_statement)
        exit(0)

    from rich.console import Console
    from rich.pretty import pprint
    from rich.rule import Rule
    from rich.syntax import Syntax
    from rich.table import Table

    console = Console(stderr=True)

    if print_messages:
        for msg in resp.messages:
            pprint(msg, console=console)

    if print_usage:
        usage = resp.usage
        table = Table(title="Usage")
        table.add_column("Metric", justify="left", no_wrap=True)
        table.add_column("Value", justify="right", no_wrap=True)
        table.add_row("Requests", str(usage.requests))
        table.add_row(
            "Request Tokens", str(usage.request_tokens) if usage.request_tokens else "?"
        )
        table.add_row(
            "Response Tokens",
            str(usage.response_tokens) if usage.response_tokens else "?",  # noqa
        )
        table.add_row(
            "Total Tokens", str(usage.total_tokens) if usage.total_tokens else "?"
        )
        console.print(table)

    console.print(Rule())
    console.print(Syntax(resp.sql_statement, "sql"))

    if save_final_prompt:
        save_final_prompt.expanduser().resolve().write_text(resp.final_prompt)


cli.add_command(semantic_catalog)
