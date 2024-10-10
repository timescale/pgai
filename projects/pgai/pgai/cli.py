import asyncio
import logging
import os
import random
import sys
from collections.abc import Sequence
from pathlib import Path

import click
import psycopg
import structlog
from dotenv import load_dotenv
from psycopg.rows import dict_row, namedtuple_row

from .__init__ import __version__
from .vectorizer.secrets import Secrets
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
        secrets = Secrets(OPENAI_API_KEY=api_key)
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


@click.command()
@click.version_option(version=__version__)
@click.option(
    "-d",
    "--db-url",
    type=click.STRING,
    envvar="VECTORIZER_DB_URL",
    default="postgres://postgres@localhost:5432/postgres",
    show_default=True,
)
@click.option(
    "--tiktoken-cache-dir",
    envvar="TIKTOKEN_CACHE_DIR",
    type=click.Path(),
    default=lambda: Path.cwd().joinpath("tiktoken_cache"),
    show_default=True,
)
@click.option("-i", "--vectorizer-id", "vectorizer_ids", type=click.INT, multiple=True)
@click.option(
    "-c", "--concurrency", type=click.IntRange(1), default=1, show_default=True
)
@click.option(
    "--log-level",
    type=click.Choice(
        ["DEBUG", "INFO", "WARN", "ERROR", "FATAL", "CRITICAL"], case_sensitive=False
    ),
    default="INFO",
)
def run(
    db_url: str,
    tiktoken_cache_dir: Path,
    vectorizer_ids: Sequence[int] | None = None,
    concurrency: int = 1,
    log_level: str = "INFO",
) -> None:
    log_level_: int = logging.getLevelNamesMapping()[log_level.upper()]
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(log_level_))

    if not tiktoken_cache_dir:
        log.critical("tiktoken_cache_dir not provided")
        sys.exit(1)
    if isinstance(tiktoken_cache_dir, str):
        tiktoken_cache_dir = Path(tiktoken_cache_dir)
    if not tiktoken_cache_dir.is_dir():
        log.critical(
            "tiktoken_cache_dir is not a directory",
            tiktoken_cache_dir=tiktoken_cache_dir,
        )
        sys.exit(1)
    os.environ["TIKTOKEN_CACHE_DIR"] = str(tiktoken_cache_dir.resolve())

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

    for vectorizer_id in vectorizer_ids:
        vectorizer = get_vectorizer(db_url, vectorizer_id)
        if vectorizer is None:
            continue
        log.info("running vectorizer", vectorizer_id=vectorizer_id)
        run_vectorizer(db_url, vectorizer, concurrency)
