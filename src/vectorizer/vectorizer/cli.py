import sys

import click
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

from .__init__ import __version__


load_dotenv()


def get_pgai_version(cur: psycopg.Cursor) -> str | None:
    cur.execute("select extversion from pg_catalog.pg_extension where extname = 'ai'")
    row = cur.fetchone()
    return row['extversion'] if row is not None else None


def get_vectorizer_ids(cur: psycopg.Cursor) -> list[int]:
    vectorizer_ids = []
    cur.execute("select id from ai.vectorizer order by random()")
    for row in cur.fetchall():
        vectorizer_ids.append(row['id'])
    return vectorizer_ids


def list_valid_vectorizer_ids(cur: psycopg.Cursor, vectorizer_ids: list[int] | tuple[int]) -> list[int]:
    valid_vectorizer_ids = []
    cur.execute("select id from ai.vectorizer where id = any(%s) order by random()", [list(vectorizer_ids),])
    for row in cur.fetchall():
        valid_vectorizer_ids.append(row['id'])
    return valid_vectorizer_ids


def vectorize(db_url: str, vectorizer_ids: list[int] | None) -> None:
    print(db_url)
    with psycopg.Connection.connect(db_url) as con:
        with con.cursor(row_factory=dict_row) as cur:
            pgai_version = get_pgai_version(cur)
            if pgai_version is None:
                click.echo('the pgai extension is not installed', err=True)
                sys.exit(1)
            else:
                click.echo(f'pgai: {pgai_version}')
            vectorizer_ids = get_vectorizer_ids(cur) if vectorizer_ids is None else list_valid_vectorizer_ids(cur, vectorizer_ids)
            for vectorizer_id in vectorizer_ids:
                click.echo(f'vectorizing {vectorizer_id}')
                # TODO: process the vectorizer


@click.command()
@click.version_option(version=__version__)
@click.option('-d', '--db-url', type=click.STRING, envvar='VECTORIZER_DB_URL',
              default='postgres://postgres@localhost:5432/postgres', show_default=True)
@click.option('-i', '--vectorizer-id', type=click.INT, multiple=True)
def run(db_url: str, vectorizer_id: list[int] | None):
    vectorizer_ids = None if vectorizer_id is None or len(vectorizer_id) == 0 else vectorizer_id
    vectorize(db_url, vectorizer_ids)
