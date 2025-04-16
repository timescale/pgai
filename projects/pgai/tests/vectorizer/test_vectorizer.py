import asyncio

import psycopg
import pytest
from psycopg.rows import namedtuple_row
from psycopg.sql import SQL, Identifier
from testcontainers.postgres import PostgresContainer  # type: ignore

import pgai
from pgai.vectorizer import Vectorizer, Worker
from pgai.vectorizer.features import Features
from pgai.vectorizer.worker_tracking import WorkerTracking

from .conftest import create_connection_url


def create_database(dbname: str, postgres_container: PostgresContainer) -> None:
    with (
        psycopg.connect(
            postgres_container.get_connection_url(), autocommit=True
        ) as con,
        con.cursor() as cur,
    ):
        cur.execute(
            SQL("drop database if exists {dbname} with (force)").format(
                dbname=Identifier(dbname)
            )
        )
        cur.execute(SQL("create database {dbname}").format(dbname=Identifier(dbname)))


async def _vectorizer_test_after_install(
    postgres_container: PostgresContainer,
    dbname: str,
    ai_extension_features: bool = False,
):
    db_url = create_connection_url(postgres_container, dbname=dbname)
    with (
        psycopg.connect(db_url, autocommit=True, row_factory=namedtuple_row) as con,
        con.cursor() as cur,
    ):
        if ai_extension_features:
            cur.execute("create extension if not exists ai cascade")
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
        additional_args = ""
        if ai_extension_features:
            additional_args = """
                , scheduling=>
                    ai.scheduling_timescaledb
                    ( interval '5m'
                    , initial_start=>'2050-01-06'::timestamptz
                    , timezone=>'America/Chicago'
                    )
                , indexing=>ai.indexing_diskann(min_rows=>10)
            """

        cur.execute(f"""
                select ai.create_vectorizer
                ( 'note0'::regclass
                , loading=>ai.loading_column('note')
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
                , formatting=>ai.formatting_python_template('$id: $chunk')
                , chunking=>ai.chunking_character_text_splitter()
                {additional_args}
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

        worker = Worker(db_url)

        # test cli.get_vectorizer_ids
        assert len(worker._get_vectorizer_ids()) == 1  # type: ignore
        assert len(worker._get_vectorizer_ids([42, 19])) == 0  # type: ignore
        assert len(worker._get_vectorizer_ids([vectorizer_id, 19])) == 1  # type: ignore
        assert len(worker._get_vectorizer_ids([vectorizer_id])) == 1  # type: ignore

        # test cli.get_vectorizer
        features = Features.for_testing_latest_version()
        vectorizer_actual: Vectorizer = worker._get_vectorizer(  # type: ignore
            vectorizer_id, features
        )
        assert vectorizer_actual is not None
        assert vectorizer_expected.source_table == vectorizer_actual.source_table  # type: ignore

        # run the vectorizer
        worker_tracking = WorkerTracking(db_url, 500, features, "0.0.1")

        await vectorizer_actual.run(db_url, features, worker_tracking, 1)

        # make sure the queue was emptied
        cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
        actual = cur.fetchone()[0]  # type: ignore
        assert actual == 0

        # make sure we got 10 rows out
        cur.execute(
            SQL("select count(*) from {target_schema}.{target_table}").format(
                target_schema=Identifier(
                    vectorizer_expected.config["destination"]["target_schema"]  # type: ignore
                ),  # type: ignore
                target_table=Identifier(
                    vectorizer_expected.config["destination"]["target_table"]  # type: ignore
                ),  # type: ignore
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
                view_schema=Identifier(
                    vectorizer_expected.config["destination"]["view_schema"]  # type: ignore
                ),  # type: ignore
                view_name=Identifier(
                    vectorizer_expected.config["destination"]["view_name"]  # type: ignore
                ),  # type: ignore
            )
        )
        actual = cur.fetchone()[0]  # type: ignore
        assert actual is True


@pytest.mark.asyncio
async def test_vectorizer_internal(postgres_container: PostgresContainer):
    db = "vcli0"
    create_database(db, postgres_container)
    _db_url = create_connection_url(postgres_container, dbname=db)
    with (
        psycopg.connect(_db_url, autocommit=True, row_factory=namedtuple_row) as con,
        con.cursor() as cur,
    ):
        cur.execute("create extension if not exists vectorscale cascade")
        pgai.install(_db_url)
        cur.execute("create extension if not exists timescaledb")
    await _vectorizer_test_after_install(postgres_container, db)


@pytest.mark.asyncio
async def test_vectorizer_weird_pk(postgres_container: PostgresContainer):
    # make sure we can handle a multi-column primary key with "interesting" data types
    # this has implications on the COPY with binary format logic in the vectorizer
    db = "vcli1"
    create_database(db, postgres_container)
    db_url = postgres_container.get_connection_url()
    with (
        psycopg.connect(db_url, autocommit=True, row_factory=namedtuple_row) as con,
        con.cursor() as cur,
    ):
        cur.execute("create extension if not exists vectorscale cascade")
        cur.execute("create extension if not exists timescaledb")
        pgai.install(db_url)
        cur.execute("drop table if exists weird")
        cur.execute("""
                create table weird
                ( a text[] not null
                , b varchar(3) not null
                , c timestamp with time zone not null
                , d tstzrange not null
                , note text not null
                -- use a different ordering for pk to ensure we handle it
                , primary key (a, c, b, d)
                )
            """)
        # create a vectorizer for the table
        cur.execute("""
                select ai.create_vectorizer
                ( 'weird'::regclass
                , loading=>ai.loading_column('note')
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
                , formatting=>ai.formatting_python_template('$chunk')
                , chunking=>ai.chunking_character_text_splitter()
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

        # test worker._get_vectorizer
        worker = Worker(db_url)
        features = Features.for_testing_latest_version()
        vectorizer_actual: Vectorizer = worker._get_vectorizer(  # type: ignore
            vectorizer_id, features
        )
        assert vectorizer_actual is not None
        assert vectorizer_expected.source_table == vectorizer_actual.source_table  # type: ignore

        # insert 7 rows into source
        cur.execute("""
                insert into weird (a, b, c, d, note)
                select
                  array['larry', 'moe', 'curly']
                , 'xyz'
                , t
                , tstzrange(t, t + interval '1d', '[)')
                , 'if two witches watch two watches, which witch watches which watch'
                from generate_series('2025-01-06'::timestamptz, '2025-01-12'::timestamptz, interval '1d') t
            """)  # noqa

        # run the vectorizer
        features = Features.for_testing_latest_version()
        worker_tracking = WorkerTracking(db_url, 500, features, "0.0.1")
        await vectorizer_actual.run(db_url, features, worker_tracking, 1)

        # make sure the queue was emptied
        cur.execute("select ai.vectorizer_queue_pending(%s)", (vectorizer_id,))
        actual = cur.fetchone()[0]  # type: ignore
        assert actual == 0

        # make sure we got 7 rows out
        cur.execute(
            SQL("select count(*) from {target_schema}.{target_table}").format(
                target_schema=Identifier(
                    vectorizer_expected.config["destination"]["target_schema"]  # type: ignore
                ),  # type: ignore
                target_table=Identifier(
                    vectorizer_expected.config["destination"]["target_table"]  # type: ignore
                ),  # type: ignore
            )
        )
        actual = cur.fetchone()[0]  # type: ignore
        assert actual == 7


@pytest.mark.asyncio
@pytest.mark.parametrize("async_install", [True, False])
async def test_vectorizer_install_twice(
    postgres_container: PostgresContainer, async_install: bool
):
    db = "ainstall2"
    create_database(db, postgres_container)
    _db_url = create_connection_url(postgres_container, dbname=db)
    if async_install:
        await pgai.ainstall(_db_url)
        await pgai.ainstall(_db_url)
    else:
        pgai.install(_db_url)
        pgai.install(_db_url)

    with pytest.raises(psycopg.errors.DuplicateObject):
        if async_install:
            await pgai.ainstall(_db_url, strict=True)
        else:
            pgai.install(_db_url, strict=True)

    # test the vectorizer
    with (
        psycopg.connect(_db_url, autocommit=True, row_factory=namedtuple_row) as con,
        con.cursor() as cur,
    ):
        cur.execute("create extension if not exists timescaledb")
    await _vectorizer_test_after_install(postgres_container, db)


@pytest.mark.postgres_params(set_executor_url=True)
@pytest.mark.asyncio
@pytest.mark.parametrize("async_install", [True, False])
async def test_vectorizer_install_need_ai_extension(
    postgres_container: PostgresContainer, async_install: bool
):
    # the pytest mark set the ai.external_functions_executor_url to http://www.example.com

    db = "need_ai_extension"
    create_database(db, postgres_container)
    _db_url = create_connection_url(postgres_container, dbname=db)
    if async_install:
        await pgai.ainstall(_db_url)
    else:
        pgai.install(_db_url)

    with (
        psycopg.connect(_db_url, autocommit=True, row_factory=namedtuple_row) as con,
        con.cursor() as cur,
    ):
        cur.execute("select extname from pg_extension where extname = 'ai'")
        result = cur.fetchone()
        assert result is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("async_install", [True, False])
async def test_vectorizer_install_no_ai_extension(
    postgres_container: PostgresContainer, async_install: bool
):
    # by default, the ai extension should not be installed
    db = "no_ai_extension"
    create_database(db, postgres_container)
    _db_url = create_connection_url(postgres_container, dbname=db)
    if async_install:
        await pgai.ainstall(_db_url)
    else:
        pgai.install(_db_url)

    with (
        psycopg.connect(_db_url, autocommit=True, row_factory=namedtuple_row) as con,
        con.cursor() as cur,
    ):
        cur.execute("select extname from pg_extension where extname = 'ai'")
        result = cur.fetchone()
        assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize("async_install", [True, False])
async def test_vectorizer_install_vector_in_different_schema(
    postgres_container: PostgresContainer, async_install: bool
):
    db = "vector_in_different_schema"
    create_database(db, postgres_container)
    _db_url = create_connection_url(postgres_container, dbname=db)

    with (
        psycopg.connect(_db_url, autocommit=True, row_factory=namedtuple_row) as con,
        con.cursor() as cur,
    ):
        cur.execute("create schema other")
        cur.execute("create extension if not exists vector schema other")
        cur.execute("create extension if not exists timescaledb")
        cur.execute(f"alter database {db} set search_path = public,other")

    if async_install:
        await pgai.ainstall(_db_url)
    else:
        pgai.install(_db_url)

    await _vectorizer_test_after_install(postgres_container, db)


async def _vectorizer_setup_simplevectorizer(
    postgres_container: PostgresContainer,
    dbname: str,
):
    db_url = create_connection_url(postgres_container, dbname=dbname)
    with (
        psycopg.connect(db_url, autocommit=True, row_factory=namedtuple_row) as con,
        con.cursor() as cur,
    ):
        table_name = "notes_simple"
        cur.execute(f"drop table if exists {table_name}")
        cur.execute(f"""
                create table {table_name}
                ( id bigint not null primary key generated always as identity
                , note text not null
                )
        """)
        # insert 5 rows into source
        cur.execute(f"""
                insert into {table_name} (note)
                select 'how much wood would a woodchuck chuck if a woodchuck could chuck wood'
                from generate_series(1, 5)
            """)  # noqa
        # insert 5 rows into source
        cur.execute(f"""
                insert into {table_name} (note)
                select 'if a woodchuck could chuck wood, a woodchuck would chuck as much wood as he could'
                from generate_series(1, 5)
            """)  # noqa

        cur.execute(f"""
                select ai.create_vectorizer
                ( '{table_name}'::regclass
                , loading=>ai.loading_column('note')
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
                , formatting=>ai.formatting_python_template('$id: $chunk')
                , chunking=>ai.chunking_character_text_splitter()
                , grant_to=>null
                , enqueue_existing=>true
                )
            """)


@pytest.mark.asyncio
async def test_vectorizer_run_once_with_shutdown(
    postgres_container: PostgresContainer,
):
    db = "run_once_with_shutdown"
    create_database(db, postgres_container)
    db_url = create_connection_url(postgres_container, dbname=db)
    await pgai.ainstall(db_url)

    await _vectorizer_setup_simplevectorizer(postgres_container, db)

    worker = Worker(db_url, once=True)
    task = asyncio.create_task(worker.run())
    await worker.request_graceful_shutdown()
    result = await asyncio.wait_for(task, timeout=300)
    assert result is None


@pytest.mark.asyncio
async def test_vectorizer_run_with_shutdown(
    postgres_container: PostgresContainer,
):
    db = "run_with_shutdown"
    create_database(db, postgres_container)
    db_url = create_connection_url(postgres_container, dbname=db)
    await pgai.ainstall(db_url)

    await _vectorizer_setup_simplevectorizer(postgres_container, db)

    worker = Worker(db_url)
    task = asyncio.create_task(worker.run())
    await worker.request_graceful_shutdown()
    result = await asyncio.wait_for(task, timeout=300)
    assert result is None
