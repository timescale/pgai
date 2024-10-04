import logging
import os
import random
import sys
from typing import Sequence

import click
import psycopg
import structlog
from psycopg.rows import dict_row, namedtuple_row
from dotenv import load_dotenv

from .__init__ import __version__
from .vectorizer import Vectorizer

load_dotenv()
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
log = structlog.get_logger()


def get_pgai_version(cur: psycopg.Cursor) -> str | None:
    cur.execute("select extversion from pg_catalog.pg_extension where extname = 'ai'")
    row = cur.fetchone()
    return row.extversion if row is not None else None


def get_vectorizer_ids(cur: psycopg.Cursor, vectorizer_ids: Sequence[int] | None = None) -> list[int]:
    valid_vectorizer_ids = []
    if vectorizer_ids is None or len(vectorizer_ids) == 0:
        cur.execute("select id from ai.vectorizer")
    else:
        cur.execute("select id from ai.vectorizer where id = any(%s)", [list(vectorizer_ids),])
    for row in cur.fetchall():
        valid_vectorizer_ids.append(row.id)
    random.shuffle(valid_vectorizer_ids)
    return valid_vectorizer_ids


def get_vectorizer(db_url, vectorizer_id: int) -> Vectorizer | None:
    with psycopg.Connection.connect(db_url, row_factory=dict_row) as con:
        with con.cursor() as cur:
            cur.execute("select pg_catalog.to_jsonb(v) as vectorizer from ai.vectorizer v where v.id = %s", (vectorizer_id,))
            row = cur.fetchone()
            if row is None:
                return None
            vectorizer = row['vectorizer']
            return Vectorizer(**vectorizer)


def vectorize(db_url: str, vectorizer_ids: list[int] | None) -> None:
    openai_api_key = os.getenv('OPENAI_API_KEY', None)
    if openai_api_key is None:
        log.critical('OPENAI_API_KEY environment variable is not set')
        sys.exit(1)
    with psycopg.Connection.connect(db_url) as con:
        with con.cursor(row_factory=namedtuple_row) as cur:
            pgai_version = get_pgai_version(cur)
            if pgai_version is None:
                log.critical('the pgai extension is not installed')
                sys.exit(1)
            vectorizer_ids = get_vectorizer_ids(cur, vectorizer_ids)
    if len(vectorizer_ids) == 0:
        log.warning('no vectorizers found')
        return
    for vectorizer_id in vectorizer_ids:
        vectorizer = get_vectorizer(db_url, vectorizer_id)
        if vectorizer is None:
            log.warning('vectorizer not found', vectorizer_id=vectorizer_id)
            continue
        log.info('running vectorizer', vectorizer_id=vectorizer_id)


@click.command()
@click.version_option(version=__version__)
@click.option('-d', '--db-url', type=click.STRING, envvar='VECTORIZER_DB_URL',
              default='postgres://postgres@localhost:5432/postgres', show_default=True)
@click.option('-i', '--vectorizer-id', type=click.INT, multiple=True)
@click.option('--log-level', type=click.Choice(['DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL', 'CRITICAL'], case_sensitive=False), default='INFO')
def run(db_url: str, vectorizer_id: Sequence[int] | None = None, log_level: str = 'INFO') -> None:
    log_level = logging.getLevelNamesMapping()[log_level.upper()]
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(log_level))
    vectorize(db_url, vectorizer_id)
