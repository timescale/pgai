import os

import psycopg
import pytest
from psycopg.rows import namedtuple_row
from psycopg.sql import SQL, Identifier

from pgai import cli

# skip tests in this module if disabled
enable_vectorizer_tool_tests = os.getenv("ENABLE_VECTORIZER_TOOL_TESTS")
if not enable_vectorizer_tool_tests or enable_vectorizer_tool_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str, dbname: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/{dbname}"


def create_database(dbname: str) -> None:
    with (
        psycopg.connect(
            db_url(user="postgres", dbname="postgres"), autocommit=True
        ) as con,
        con.cursor() as cur,
    ):
        cur.execute(
            SQL("drop database if exists {dbname} with (force)").format(
                dbname=Identifier(dbname)
            )
        )
        cur.execute(SQL("create database {dbname}").format(dbname=Identifier(dbname)))


def test_vectorizer_internal():
    db = "vcli0"
    create_database(db)
    _db_url = db_url("postgres", db)
    with (
        psycopg.connect(_db_url, autocommit=True, row_factory=namedtuple_row) as con,
        con.cursor() as cur,
    ):
        cur.execute("create extension if not exists vectorscale cascade")
        pgai_version = cli.get_pgai_version(cur)
        assert pgai_version is None
        cur.execute("create extension if not exists ai cascade")
        pgai_version = cli.get_pgai_version(cur)
        assert pgai_version is not None
        assert len(cli.get_vectorizer_ids(_db_url)) == 0
        assert len(cli.get_vectorizer_ids(_db_url, [42, 19])) == 0
        cur.execute("create extension if not exists timescaledb")
        cur.execute("drop table if exists note0")
        cur.execute("""
                create table note0
                ( id bigint not null primary key generated always as identity
                , note text not null
                )
            """)
        # insert 5 rows into source
        cur.execute("""
                insert into note0 (note)
                select 'how much wood would a woodchuck chuck if a woodchuck could chuck wood'
                from generate_series(1, 5)
            """)  # noqa
        # insert 5 rows into source
        cur.execute("""
                insert into note0 (note)
                select 'if a woodchuck could chuck wood, a woodchuck would chuck as much wood as he could'
                from generate_series(1, 5)
            """)  # noqa
        # create a vectorizer for the table
        cur.execute("""
                select ai.create_vectorizer
                ( 'note0'::regclass
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
                , formatting=>ai.formatting_python_template('$id: $chunk')
                , chunking=>ai.chunking_character_text_splitter('note')
                , scheduling=>
                    ai.scheduling_timescaledb
                    ( interval '5m'
                    , initial_start=>'2050-01-06'::timestamptz
                    , timezone=>'America/Chicago'
                    )
                , indexing=>ai.indexing_diskann(min_rows=>10)
                , grant_to=>null
                , enqueue_existing=>true
                )
            """)
        row = cur.fetchone()
        if row is None:
            raise ValueError("vectorizer_id is None")
        vectorizer_id = row[0]
        if not isinstance(vectorizer_id, int):
            raise ValueError("vectorizer_id is not an integer")

        cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
        vectorizer_expected = cur.fetchone()

        # test cli.get_vectorizer_ids
        assert len(cli.get_vectorizer_ids(_db_url)) == 1
        assert len(cli.get_vectorizer_ids(_db_url, [42, 19])) == 0
        assert len(cli.get_vectorizer_ids(_db_url, [vectorizer_id, 19])) == 1
        assert len(cli.get_vectorizer_ids(_db_url, [vectorizer_id])) == 1

        # test cli.get_vectorizer
        vectorizer_actual = cli.get_vectorizer(_db_url, vectorizer_id)
        assert vectorizer_actual is not None
        assert vectorizer_expected.source_table == vectorizer_actual.source_table  # type: ignore

        # run the vectorizer
        cli.run_vectorizer(_db_url, vectorizer_actual, 1)

        # make sure the queue was emptied
        cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
        actual = cur.fetchone()[0]  # type: ignore
        assert actual == 0

        # make sure we got 10 rows out
        cur.execute(
            SQL("select count(*) from {target_schema}.{target_table}").format(
                target_schema=Identifier(vectorizer_expected.target_schema),  # type: ignore
                target_table=Identifier(vectorizer_expected.target_table),  # type: ignore
            )
        )
        actual = cur.fetchone()[0]  # type: ignore
        assert actual == 10

        # make sure the chunks were formatted correctly
        cur.execute(
            SQL("""
                select count(*) = count(*)
                filter (where chunk = format('%s: %s', id, note))
                from {view_schema}.{view_name}
                """).format(
                view_schema=Identifier(vectorizer_expected.view_schema),  # type: ignore
                view_name=Identifier(vectorizer_expected.view_name),  # type: ignore
            )
        )
        actual = cur.fetchone()[0]  # type: ignore
        assert actual is True
