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
from ddtrace.trace import tracer
from dotenv import find_dotenv, load_dotenv
from pytimeparse import parse  # type: ignore

from .__init__ import __version__

load_dotenv(dotenv_path=find_dotenv(usecwd=True))

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
    """Manage semantic catalogs for PostgreSQL databases.

    Semantic catalogs store metadata about database objects along with natural language
    descriptions and vector embeddings, enabling natural language queries about database
    schema and AI-generated SQL.
    """


@semantic_catalog.command()
@click.option(
    "-d",
    "--db-url",
    type=click.STRING,
    help="The connection URL to the database to find objects in.",
    envvar="TARGET_DB",
)
@click.option(
    "-m",
    "--model",
    type=click.STRING,
    default="openai:gpt-4.1",
    show_default=True,
    help="The LLM model to generate descriptions (format: provider:model).",
)
@click.option(
    "--include-schema",
    type=click.STRING,
    default=None,
    help="Regex pattern to include schemas (e.g. 'public|app_.*').",
)
@click.option(
    "--exclude-schema",
    type=click.STRING,
    default=None,
    help="Regex pattern to exclude schemas (e.g. 'pg_.*|information_schema').",
)
@click.option(
    "--include-table",
    type=click.STRING,
    default=None,
    help="Regex pattern to include tables (e.g. 'user.*|product.*').",
)
@click.option(
    "--exclude-table",
    type=click.STRING,
    default=None,
    help="Regex pattern to exclude tables (e.g. 'temp_.*|_bak$').",
)
@click.option(
    "--include-view",
    type=click.STRING,
    default=None,
    help="Regex pattern to include views (e.g. 'v_.*|report_.*').",
)
@click.option(
    "--exclude-view",
    type=click.STRING,
    default=None,
    help="Regex pattern to exclude views (e.g. 'v_temp_.*').",
)
@click.option(
    "--include-proc",
    type=click.STRING,
    default=None,
    help="Regex pattern to include procedures/functions (e.g. 'fn_.*|sp_.*').",
)
@click.option(
    "--exclude-proc",
    type=click.STRING,
    default=None,
    help="Regex pattern to exclude procedures/functions (e.g. 'internal_.*').",
)
@click.option(
    "--include-extension",
    type=click.STRING,
    multiple=True,
    default=None,
    help="The name of an extension whose objects should not be excluded",
)
@click.option(
    "-f",
    "--yaml-file",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="Path to output YAML file (default: print to stdout).",
)
@click.option(
    "-a",
    "--append",
    is_flag=True,
    help="Append to the output file instead of overwriting it.",
)
@click.option(
    "--sample-size",
    type=click.INT,
    default=3,
    help="Number of sample rows to retrieve from tables/views.",
)
@click.option(
    "--batch-size",
    type=click.INT,
    default=5,
    help="Number of database objects to process in each LLM request.",
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
    help="Path to log file for detailed logging.",
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARN", "ERROR", "FATAL", "CRITICAL"], case_sensitive=False
    ),
    default="INFO",
)
@click.option(
    "--request-limit",
    type=click.INT,
    default=None,
    help="Maximum number of LLM requests allowed (for cost control).",
)
@click.option(
    "--total-tokens-limit",
    type=click.INT,
    default=None,
    help="Maximum total LLM tokens allowed (for cost control).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Find and list objects that would be described, but do not describe them.",
)
def describe(
    db_url: str | None,
    model: str,
    include_schema: str | None = None,
    exclude_schema: str | None = None,
    include_table: str | None = None,
    exclude_table: str | None = None,
    include_view: str | None = None,
    exclude_view: str | None = None,
    include_proc: str | None = None,
    exclude_proc: str | None = None,
    include_extension: list[str] | None = None,
    yaml_file: Path | None = None,
    append: bool = False,
    sample_size: int = 3,
    batch_size: int = 5,
    quiet: bool = False,
    log_file: Path | None = None,
    log_level: str | None = "INFO",
    request_limit: int | None = None,
    total_tokens_limit: int | None = None,
    dry_run: bool = False,
) -> None:
    """Generate natural language descriptions for database objects.

    Uses AI to create human-readable descriptions of database objects including
    tables, views, and procedures. These descriptions can be used to populate
    a semantic catalog for natural language queries and SQL generation.

    The command connects to the specified database, extracts schema information for
    matching objects, and uses an LLM to generate comprehensive descriptions.
    Results are exported to YAML format.

    Filtering options allow you to include or exclude database objects based on
    regular expression patterns applied to schema, table, view, and procedure names.
    """
    if log_file:
        import logging

        logging.basicConfig(
            level=get_log_level(log_level or "INFO"),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file.expanduser().resolve()),
            ],
        )

    if not db_url:
        print(
            "--db-url must be specified or TARGET_DB environment variable defined",
            file=sys.stderr,
        )
        exit(1)

    from pydantic_ai.usage import UsageLimits
    from rich.console import Console

    from pgai.semantic_catalog.describe import describe

    if yaml_file:
        yaml_file = yaml_file.expanduser().resolve()

    with (
        sys.stdout
        if not yaml_file
        else yaml_file.open(mode="a" if append else "w") as f
    ):
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
                include_extensions=[x for x in include_extension]
                if include_extension
                else None,
                usage_limits=UsageLimits(
                    request_limit=request_limit,
                    total_tokens_limit=total_tokens_limit,
                ),
                sample_size=sample_size,
                batch_size=batch_size,
                dry_run=dry_run,
            )
        )


@semantic_catalog.command()
@click.option(
    "-c",
    "--catalog_db_url",
    type=click.STRING,
    help="The connection URL to the database the semantic catalog is in.",
    envvar="CATALOG_DB",
)
@click.option(
    "-n",
    "--catalog-name",
    type=click.STRING,
    default="default",
    show_default=True,
    help="Name of the semantic catalog to use.",
)
@click.option(
    "-e",
    "--embed-config",
    type=click.STRING,
    default=None,
    help="Name of the embedding configuration to use. If not specified, uses all available configurations.",  # noqa: E501
)
@click.option(
    "-b",
    "--batch-size",
    type=click.INT,
    default=None,
    help="Number of items to process in each vectorization batch (default: 32).",
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
    catalog_db_url: str | None,
    catalog_name: str | None,
    embed_config: str | None,
    batch_size: int | None = None,
    quiet: bool = False,
    log_file: Path | None = None,
    log_level: str | None = "INFO",
) -> None:
    """Generate vector embeddings for items in the semantic catalog.

    Processes all database objects, SQL examples, and facts in the semantic catalog
    that don't yet have embeddings for the specified embedding configuration.

    The embeddings are used for semantic search capabilities, allowing natural
    language queries about the database schema and context for SQL generation.

    If no embedding configuration is specified, all configurations in the
    catalog will be used for vectorization.

    Examples:
        # Vectorize all items using all embedding configurations
        pgai semantic-catalog vectorize

        # Vectorize using a specific embedding configuration
        pgai semantic-catalog vectorize --embed-config openai_embeddings
    """
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

    catalog_db_url = catalog_db_url if catalog_db_url else os.getenv("TARGET_DB")
    if not catalog_db_url:
        print(
            (
                "--catalog-db-url must be specified or CATALOG_DB or TARGET_DB "
                "environment variable defined"
            ),
            file=sys.stderr,
        )
        exit(1)

    catalog_name = catalog_name or "default"
    batch_size = batch_size if batch_size is not None else 32

    async def do():
        from pgai.semantic_catalog import from_name

        async with await psycopg.AsyncConnection.connect(catalog_db_url) as con:
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
    "-c",
    "--catalog-db-url",
    type=click.STRING,
    help="The connection URL to the database to create the semantic catalog in.",
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
    catalog_db_url: str | None,
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
    """Create a new semantic catalog with embedding configuration.

    Creates a semantic catalog in the database with the specified parameters.
    The catalog requires at least one embedding configuration to enable semantic
    search capabilities.

    The embedding configuration specifies which embedding provider and model
    to use for generating vector embeddings, along with the vector dimensions.

    \b
    Supported providers:
    - `openai` (requires API key)
    - `ollama`
    - `sentence_transformers`

    \b
    Supported models:
    - OpenAI: https://platform.openai.com/docs/guides/embeddings#embedding-models
    - Ollama: https://ollama.com/search?c=embedding
    - Sentence Transformers:
        - https://www.sbert.net/docs/sentence_transformer/pretrained_models.html
        - https://huggingface.co/models?library=sentence-transformers

    Examples:

        \b
        # Create a catalog with OpenAI embeddings
        pgai semantic-catalog create --provider openai --model text-embedding-3-small

        \b
        # Create a catalog with custom embedding name
        pgai semantic-catalog create --catalog-name my_catalog --embed-config custom_embeddings
    """  # noqa: E501
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

    from pgai.semantic_catalog.vectorizer import embedding_config_from_dict

    d = dict(
        implementation=provider.lower(),
        model=str(model),
        dimensions=int(vector_dimensions),
    )
    if base_url:
        d["base_url"] = base_url
    if api_key_name:
        d["api_key_name"] = api_key_name
    config = embedding_config_from_dict(d)

    catalog_db_url = catalog_db_url if catalog_db_url else os.getenv("TARGET_DB")
    if not catalog_db_url:
        print(
            (
                "--catalog-db-url must be specified or CATALOG_DB or TARGET_DB "
                "environment variables defined"
            ),
            file=sys.stderr,
        )
        exit(1)

    import pgai

    pgai.install(catalog_db_url, strict=False)

    async def do():
        from pgai.semantic_catalog import create

        async with await psycopg.AsyncConnection.connect(catalog_db_url) as con:
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
    help="The connection URL to the database the database to generate sql for.",
    envvar="TARGET_DB",
)
@click.option(
    "-c",
    "--catalog-db-url",
    type=click.STRING,
    help="The connection URL to the database the semantic catalog is in.",
    envvar="CATALOG_DB",
)
@click.option(
    "-f",
    "--yaml-file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="The path to a yaml file.",
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
    db_url: str | None,
    catalog_db_url: str | None,
    yaml_file: Path | None,
    catalog_name: str | None,
    embed_config: str | None,
    batch_size: int | None = None,
    quiet: bool = False,
    log_file: Path | None = None,
    log_level: str | None = "INFO",
) -> None:
    """Import catalog items from a YAML file into a semantic catalog.

    Reads catalog items (tables, views, procedures, SQL examples, facts) from a YAML file
    and imports them into the specified semantic catalog. After importing, it generates
    vector embeddings for the imported items.

    The YAML file should be in the format produced by the 'describe' or 'export' commands.
    If no YAML file is provided, input is read from stdin.

    Examples:

        \b
        # Import from a YAML file
        pgai semantic-catalog import --yaml-file descriptions.yaml

        \b
        # Import and vectorize using a specific embedding configuration
        pgai semantic-catalog import --yaml-file descriptions.yaml --embed-config openai_embeddings

        \b
        # Import from stdin
        cat descriptions.yaml | pgai semantic-catalog import
    """  # noqa: E501
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

    if not db_url:
        print(
            "--db-url must be specified or TARGET_DB " "environment variable defined",
            file=sys.stderr,
        )
        exit(1)

    catalog_name = catalog_name or "default"
    if yaml_file:
        yaml_file = yaml_file.expanduser().resolve()
        assert yaml_file.is_file(), "invalid yaml file"

    async def do1(ccon: psycopg.AsyncConnection, tcon: psycopg.AsyncConnection):
        from pgai.semantic_catalog import from_name

        console.status(f"finding '{catalog_name}' catalog...")
        sc = await from_name(ccon, catalog_name)
        with sys.stdin if not yaml_file else yaml_file.open(mode="r") as r:
            await sc.import_catalog(ccon, tcon, r, embed_config, batch_size, console)

    async def do() -> None:
        if catalog_db_url:
            async with (
                await psycopg.AsyncConnection.connect(db_url) as tcon,
                await psycopg.AsyncConnection.connect(catalog_db_url) as ccon,
            ):
                await do1(ccon, tcon)
        else:
            async with await psycopg.AsyncConnection.connect(db_url) as con:
                await do1(con, con)

    asyncio.run(do())


@semantic_catalog.command(name="export")
@click.option(
    "-c",
    "--catalog-db-url",
    type=click.STRING,
    help="The connection URL to the database the semantic catalog is in.",
    envvar="CATALOG_DB",
)
@click.option(
    "-f",
    "--yaml-file",
    type=click.Path(dir_okay=False, path_type=Path),
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
    catalog_db_url: str | None,
    yaml_file: Path | None,
    catalog_name: str | None,
    quiet: bool = False,
    log_file: Path | None = None,
    log_level: str | None = "INFO",
) -> None:
    """Export catalog items from a semantic catalog to a YAML file.

    Exports all database objects (tables, views, procedures), SQL examples,
    and facts from the semantic catalog to a YAML file. This YAML can be used
    to recreate the catalog in another database or as a backup.

    If no YAML file is provided, output is written to stdout.

    Examples:

        \b
        # Export to a YAML file
        pgai semantic-catalog export --yaml-file catalog_backup.yaml

        \b
        # Export a specific catalog
        pgai semantic-catalog export --catalog-name my_catalog --yaml-file my_catalog.yaml

        \b
        # Export to stdout
        pgai semantic-catalog export | tee catalog_backup.yaml
    """  # noqa: E501
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

    catalog_db_url = catalog_db_url if catalog_db_url else os.getenv("TARGET_DB")
    if not catalog_db_url:
        print(
            (
                "--catalog-db-url must be specified or CATALOG_DB or TARGET_DB "
                "environment variables defined"
            ),
            file=sys.stderr,
        )
        exit(1)

    catalog_name = catalog_name or "default"
    if yaml_file:
        yaml_file = yaml_file.expanduser().resolve()

    async def do():
        from pgai.semantic_catalog import from_name

        async with await psycopg.AsyncConnection.connect(catalog_db_url) as ccon:
            console.status(f"finding '{catalog_name}' catalog...")
            sc = await from_name(ccon, catalog_name)
            console.status("exporting semantic catalog to file...")
            with sys.stdout if not yaml_file else yaml_file.open(mode="w") as w:
                await sc.export_catalog(ccon, w)

    asyncio.run(do())


@semantic_catalog.command()
@click.option(
    "-d",
    "--db-url",
    type=click.STRING,
    help="Connection URL to the target database where SQL will be executed.",
    envvar="TARGET_DB",
)
@click.option(
    "-c",
    "--catalog-db-url",
    type=click.STRING,
    help="Connection URL to the database containing the semantic catalog.",
    envvar="CATALOG_DB",
)
@click.option(
    "-m",
    "--model",
    type=click.STRING,
    default="openai:gpt-4.1",
    show_default=True,
    help="LLM model to use for SQL generation (format: provider:model).",
)
@click.option(
    "-n",
    "--catalog-name",
    type=click.STRING,
    default="default",
    show_default=True,
    help="Name of the semantic catalog to use.",
)
@click.option(
    "-e",
    "--embed-config",
    type=click.STRING,
    default=None,
    help="Name of the embedding configuration to use. If not specified, uses the first available configuration.",  # noqa: E501
)
@click.option(
    "-p",
    "--prompt",
    type=click.STRING,
    default=None,
    help="Natural language description of the SQL query you want to generate (e.g., 'Find all orders placed last month')",  # noqa: E501
    required=True,
)
@click.option(
    "--iteration-limit",
    type=click.INT,
    default=5,
    show_default=True,
    help="Maximum number of refinement attempts when generating SQL",
)
@click.option(
    "-s",
    "--sample-size",
    type=click.INT,
    default=3,
    show_default=True,
    help="Number of sample rows to include for each table/view in the context",
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
    "--print-query-plan",
    is_flag=True,
    help="Print the query plan in json format.",
)
@click.option(
    "--save-final-prompt",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="The path to a file to write the final prompt to.",
)
@click.option(
    "--request-limit",
    type=click.INT,
    default=None,
    help="Maximum number of LLM requests allowed",
)
@click.option(
    "--total-tokens-limit",
    type=click.INT,
    default=None,
    help="Maximum total LLM tokens allowed",
)
def generate_sql(
    db_url: str | None,
    catalog_db_url: str | None,
    model: str,
    catalog_name: str | None,
    embed_config: str | None,
    prompt: str,
    iteration_limit: int = 10,
    sample_size: int = 3,
    quiet: bool = False,
    log_file: Path | None = None,
    log_level: str | None = "INFO",
    print_messages: bool = False,
    print_usage: bool = False,
    print_query_plan: bool = False,
    save_final_prompt: Path | None = None,
    request_limit: int | None = None,
    total_tokens_limit: int | None = None,
) -> None:
    """Generate SQL based on a natural language prompt using the semantic catalog.

    Uses AI to generate a SQL statement that fulfills the user's request, based on
    context from the semantic catalog. The SQL is validated against the target database
    to ensure it's correct.

    The semantic catalog provides context about the database schema, including table
    structures, column descriptions, and example SQL queries. This context helps the
    AI model generate accurate SQL statements.

    Valid models for `--model` can be found at:
    https://ai.pydantic.dev/api/models/base/#pydantic_ai.models.KnownModelName

    Examples:

        \b
        # Generate SQL for a simple query
        pgai semantic-catalog generate-sql --prompt "Find all users who signed up last month"

        \b
        # Use a specific model and limit iterations
        pgai semantic-catalog generate-sql --model anthropic:claude-3-opus-20240229 \\
            --prompt "Count orders by product category for Q1 2023" \\
            --iteration-limit 3

        \b
        # Save the final prompt for debugging
        pgai semantic-catalog generate-sql --prompt "Find inactive customers" \\
            --save-final-prompt debug_prompt.txt
    """  # noqa: E501
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

    if db_url is None:
        print(
            "--db-url must be specified or TARGET_DB environment variables defined",
            file=sys.stderr,
        )
        exit(1)

    catalog_name = catalog_name or "default"
    from pydantic_ai.usage import UsageLimits

    from pgai.semantic_catalog import from_name
    from pgai.semantic_catalog.gen_sql import GenerateSQLResponse

    async def do1(
        ccon: psycopg.AsyncConnection, tcon: psycopg.AsyncConnection
    ) -> GenerateSQLResponse:
        sc = await from_name(ccon, catalog_name)
        return await sc.generate_sql(
            ccon,
            tcon,
            model=model,  # pyright: ignore [reportArgumentType]
            prompt=prompt,  # pyright: ignore [reportArgumentType]
            usage_limits=UsageLimits(
                request_limit=request_limit,
                total_tokens_limit=total_tokens_limit,
            ),
            embedding_name=embed_config,
            iteration_limit=iteration_limit,
            sample_size=sample_size,
        )

    async def do() -> GenerateSQLResponse:
        if catalog_db_url:
            async with (
                await psycopg.AsyncConnection.connect(db_url) as tcon,
                await psycopg.AsyncConnection.connect(catalog_db_url) as ccon,
            ):
                return await do1(ccon, tcon)
        else:
            async with await psycopg.AsyncConnection.connect(db_url) as con:
                return await do1(con, con)

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

    if print_query_plan:
        from rich import print_json

        print_json(data=resp.query_plan)

    if print_usage:
        usage = resp.usage
        table = Table(title="Usage")
        table.add_column("Metric", justify="left", no_wrap=True)
        table.add_column("Value", justify="right", no_wrap=True)
        table.add_row("Requests", str(usage.requests))
        table.add_row(
            "Request Tokens",
            str(usage.request_tokens) if usage.request_tokens else "?",  # noqa: E501
        )
        table.add_row(
            "Response Tokens",
            str(usage.response_tokens) if usage.response_tokens else "?",  # noqa
        )
        table.add_row(
            "Total Tokens",
            str(usage.total_tokens) if usage.total_tokens else "?",  # noqa: E501
        )
        console.print(table)

    console.print(Rule())
    console.print(Syntax(resp.sql_statement, "sql", word_wrap=True))

    if save_final_prompt:
        save_final_prompt.expanduser().resolve().write_text(resp.final_prompt)


@semantic_catalog.command()
@click.option(
    "-d",
    "--db-url",
    type=click.STRING,
    help="The connection URL to the target database.",
    envvar="TARGET_DB",
)
@click.option(
    "-c",
    "--catalog-db-url",
    type=click.STRING,
    help="The connection URL to the database the semantic catalog is in.",
    envvar="CATALOG_DB",
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
    help="Natural language query to search for related database objects (e.g., 'customer orders')",  # noqa: E501
    required=True,
)
@click.option(
    "-s",
    "--sample-size",
    type=click.INT,
    default=3,
    show_default=True,
    help="Number of sample rows to include for each table/view in the results",
)
@click.option(
    "--render",
    is_flag=True,
    help="Render the prompts for matches",
)
def search(
    db_url: str | None,
    catalog_db_url: str | None,
    catalog_name: str | None,
    embed_config: str | None,
    prompt: str,
    sample_size: int = 3,
    render: bool = False,
) -> None:
    """Search the semantic catalog using natural language queries.

    Performs a semantic search across database objects, SQL examples, and facts
    in the semantic catalog based on a natural language prompt. Results are ranked
    by semantic similarity to the query.

    For each matching database object, the command displays its schema information
    and sample data (if available). For SQL examples and facts, it displays their
    contents.

    This command is useful for exploring the database schema using natural language
    and finding relevant examples that can be adapted for your own queries.

    Examples:

        \b
        # Search for objects related to users
        pgai semantic-catalog search --prompt "user accounts"

        \b
        # Search with a specific question
        pgai semantic-catalog search --prompt "How are orders related to customers?"

        \b
        # Include more sample data in results
        pgai semantic-catalog search --prompt "product inventory" --sample-size 5
    """
    catalog_name = catalog_name or "default"

    from rich.console import Console

    console = Console()

    if db_url is None:
        print(
            "--db-url must be specified or TARGET_DB environment variables defined",
            file=sys.stderr,
        )
        exit(1)

    from pgai.semantic_catalog import from_name
    from pgai.semantic_catalog.models import Fact, ObjectDescription, SQLExample

    async def do1(ccon: psycopg.AsyncConnection, tcon: psycopg.AsyncConnection) -> None:
        nonlocal embed_config
        sc = await from_name(ccon, catalog_name)
        if not embed_config:
            embeddings = await sc.list_embeddings(ccon)
            assert len(embeddings) > 0
            embed_config = embeddings[0][0]
        # objects
        obj_matches: list[ObjectDescription] = await sc.search_objects(
            ccon, embedding_name=embed_config, query=prompt, limit=5
        )
        # sql examples
        sql_matches: list[SQLExample] = await sc.search_sql_examples(
            ccon, embedding_name=embed_config, query=prompt, limit=5
        )
        # facts
        fact_matches: list[Fact] = await sc.search_facts(
            ccon, embedding_name=embed_config, query=prompt, limit=5
        )

        from rich.rule import Rule
        from rich.table import Table

        table = Table(title="Matches", expand=True)
        table.add_column("ID", justify="right")
        table.add_column("Item", justify="left", overflow="ellipsis")
        table.add_column("Description", justify="left", overflow="ellipsis")
        for m in obj_matches:
            table.add_row(str(m.id), ".".join(m.objnames), m.description)
        for m in sql_matches:
            table.add_row(str(m.id), m.sql, m.description)
        for m in fact_matches:
            table.add_row(str(m.id), "", m.description)
        console.print(table)

        if not render:
            return

        for obj in await sc.load_objects(
            ccon,
            tcon,
            obj_matches,
            sample_size,
        ):
            console.print(Rule())
            console.print(sc.render_objects([obj]))
        for ex in sql_matches:
            console.print(Rule())
            console.print(sc.render_sql_examples([ex]))
        for fact in fact_matches:
            console.print(Rule())
            console.print(sc.render_facts([fact]))

    async def do() -> None:
        if catalog_db_url:
            async with (
                await psycopg.AsyncConnection.connect(db_url) as tcon,
                await psycopg.AsyncConnection.connect(catalog_db_url) as ccon,
            ):
                await do1(ccon, tcon)
        else:
            async with await psycopg.AsyncConnection.connect(db_url) as con:
                await do1(con, con)

    asyncio.run(do())


@semantic_catalog.command()
@click.option(
    "-d",
    "--db-url",
    type=click.STRING,
    help="Connection URL to the target database where SQL will be executed.",
    envvar="TARGET_DB",
)
@click.option(
    "-c",
    "--catalog-db-url",
    type=click.STRING,
    help="Connection URL to the database containing the semantic catalog.",
    envvar="CATALOG_DB",
)
@click.option(
    "-n",
    "--catalog-name",
    type=click.STRING,
    default="default",
    show_default=True,
    help="Name of the semantic catalog to use.",
)
@click.option(
    "-m",
    "--mode",
    type=click.Choice(["fix-ids", "fix-names"], case_sensitive=False),
    default="fix-ids",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Find and list objects that would be described, but do not describe them.",
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
def fix(
    db_url: str | None,
    catalog_db_url: str | None,
    catalog_name: str | None,
    mode: str = "fix-ids",
    dry_run: bool = False,
    quiet: bool = False,
    log_file: Path | None = None,
    log_level: str | None = "INFO",
) -> None:
    """Fix database object references in the semantic catalog.

    Database objects like tables, views, or columns can have their internal IDs or
    names changed when database operations occur (like dumps/restores, renames, or
    schema changes). This command updates the semantic catalog to maintain proper
    references to these objects.

    Two fix modes are supported:

    - fix-ids: Updates the internal PostgreSQL IDs in the semantic catalog to match
      the current values in the target database.

    - fix-names: Updates the object name identifiers in the semantic catalog to match
      the current values in the target database.

    For each object in the semantic catalog:
    - If the object no longer exists in the target database, it will be deleted
    - If the object's identifiers don't match the current values, they will be updated
    - If the object's identifiers already match, it will be left unchanged

    Examples:

        \b
        # Fix internal IDs in the semantic catalog
        pgai semantic-catalog fix --mode fix-ids

        \b
        # Run a dry-run to see what would be changed without making changes
        pgai semantic-catalog fix --mode fix-names --dry-run
    """
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

    console = Console(stderr=True, quiet=quiet)

    if not db_url:
        print(
            "--db-url must be specified or TARGET_DB environment variable defined",
            file=sys.stderr,
        )
        exit(1)

    catalog_name = catalog_name or "default"
    if mode not in {
        "fix-ids",
        "fix-names",
    }:
        print('mode must be "fix-ids" or "fix-names"', file=sys.stderr)
        exit(1)

    async def do1(ccon: psycopg.AsyncConnection, tcon: psycopg.AsyncConnection):
        from pgai.semantic_catalog import from_name

        console.status(f"finding '{catalog_name}' catalog...")
        sc = await from_name(ccon, catalog_name)
        match mode:
            case "fix-ids":
                await sc.fix_ids(ccon, tcon, dry_run, console)
            case "fix-names":
                await sc.fix_names(ccon, tcon, dry_run, console)
            case _:
                raise ValueError(f"mode must be 'fix-ids' or 'fix-names': {mode}")

    async def do() -> None:
        if catalog_db_url:
            async with (
                await psycopg.AsyncConnection.connect(db_url) as tcon,
                await psycopg.AsyncConnection.connect(catalog_db_url) as ccon,
            ):
                await do1(ccon, tcon)
        else:
            async with await psycopg.AsyncConnection.connect(db_url) as con:
                await do1(con, con)

    asyncio.run(do())


cli.add_command(semantic_catalog)
