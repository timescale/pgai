import os
import subprocess
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import namedtuple_row

# skip tests in this module if disabled
enable_vectorizer_tool_tests = os.getenv("ENABLE_VECTORIZER_TOOL_TESTS")
if not enable_vectorizer_tool_tests or enable_vectorizer_tool_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str, dbname: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/{dbname}"


def create_database(dbname: str) -> None:
    with psycopg.connect(db_url(user="postgres", dbname="postgres"), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute(f"drop database if exists {dbname} with (force)")
            cur.execute(f"create database {dbname}")


def vectorizer_src_dir() -> Path:
    p = (Path(__file__)
         .parent  # vectorizer_tool
         .parent  # tests
         .parent  # project root
         .joinpath("src", "vectorizer").resolve())
    return p


@pytest.fixture(scope="module", autouse=True)
def create_tiktoken_cache_dir_if_missing() -> None:
    d = vectorizer_src_dir().joinpath("tiktoken_cache").resolve()
    if not d.is_dir():
        d.mkdir(exist_ok=True, parents=True)


def test_bad_db_url():
    _db_url = db_url("postgres", "this_is_not_a_db")
    env = os.environ.copy()
    env["VECTORIZER_DB_URL"] = _db_url
    env["OPENAI_API_KEY"] = "this_is_not_a_key"
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run("python3 -m vectorizer",
                       shell=True,
                       check=True,
                       text=True,
                       capture_output=True,
                       env=env,
                       cwd=vectorizer_src_dir(),
                       )
    env.pop("VECTORIZER_DB_URL")
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(f"python3 -m vectorizer -d '{_db_url}'",
                       shell=True,
                       check=True,
                       text=True,
                       capture_output=True,
                       env=env,
                       cwd=vectorizer_src_dir(),
                       )


def test_pgai_not_installed():
    db = "vcli1"
    create_database(db)
    _db_url = db_url("postgres", db)
    env = os.environ.copy()
    env["VECTORIZER_DB_URL"] = _db_url
    env["OPENAI_API_KEY"] = "this_is_not_a_key"
    p = subprocess.run("python3 -m vectorizer",
                       shell=True,
                       capture_output=True,
                       text=True,
                       env=env,
                       cwd=vectorizer_src_dir(),
                       )
    assert p.returncode == 1
    assert "the pgai extension is not installed" in str(p.stdout)
    env.pop("VECTORIZER_DB_URL")
    p = subprocess.run(f"python3 -m vectorizer -d '{_db_url}'",
                       shell=True,
                       capture_output=True,
                       text=True,
                       env=env,
                       cwd=vectorizer_src_dir(),
                       )
    assert p.returncode == 1
    assert "the pgai extension is not installed" in str(p.stdout)


def test_vectorizer_cli():
    db = "vcli2"
    create_database(db)
    _db_url = db_url("postgres", db)
    with psycopg.connect(_db_url, autocommit=True, row_factory=namedtuple_row) as con:
        with con.cursor() as cur:
            cur.execute("create extension if not exists vectorscale cascade")
            cur.execute("create extension if not exists ai cascade")
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
            """)
            # insert 5 rows into source
            cur.execute("""
                insert into note0 (note)
                select 'if a woodchuck could chuck wood, a woodchuck would chuck as much wood as he could'
                from generate_series(1, 5)
            """)
            # create a vectorizer for the table
            cur.execute("""
                select ai.create_vectorizer
                ( 'note0'::regclass
                , embedding=>ai.embedding_openai('text-embedding-3-small', 3)
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
            vectorizer_id = cur.fetchone()[0]
            cur.execute("select * from ai.vectorizer where id = %s", (vectorizer_id,))
            vectorizer = cur.fetchone()

    env = os.environ.copy()
    env["VECTORIZER_DB_URL"] = _db_url
    subprocess.run(f"python3 -m vectorizer -i {vectorizer_id}",
        shell=True,
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd=vectorizer_src_dir(),
        )

    with psycopg.connect(_db_url, autocommit=True, row_factory=namedtuple_row) as con:
        with con.cursor() as cur:
            cur.execute(f"""
                select count(*)
                from {vectorizer.target_schema}.{vectorizer.target_table}
            """)
            count = cur.fetchone()[0]
            assert count == 10
