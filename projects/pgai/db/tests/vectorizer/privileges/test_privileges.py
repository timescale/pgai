import os
import subprocess
from pathlib import Path, PosixPath

import psycopg
import pytest

import pgai

# skip tests in this module if disabled
enable_privileges_tests = os.getenv("ENABLE_PRIVILEGES_TESTS")
if enable_privileges_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str, dbname: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/{dbname}"


def where_am_i() -> str:
    if "WHERE_AM_I" in os.environ and os.environ["WHERE_AM_I"] == "docker":
        return "docker"
    return "host"


def docker_dir() -> str:
    return str(
        PosixPath("/").joinpath(
            "pgai", "projects", "pgai", "db", "tests", "vectorizer", "privileges"
        )
    )


def host_dir() -> Path:
    return Path(__file__).parent.absolute()


def psql_file(user, dbname, file: str) -> None:
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url(user, dbname)}"''',
            "-v ON_ERROR_STOP=1",
            "-X",
            f"-f {docker_dir()}/{file}",
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-db {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


@pytest.fixture(scope="module", autouse=True)
def init():
    psql_file("postgres", "postgres", "init0.sql")
    pgai.install(db_url("alice", "privs"))
    psql_file("alice", "privs", "init1.sql")


def test_jill_privileges():
    psql_file("jill", "privs", "jill.sql")


def test_create_vectorizer_privileges():
    # set up role "base" and role "member", which is member of base
    with psycopg.connect(db_url("postgres", "postgres"), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("drop database if exists vec_priv;")
            cur.execute(
                """
                drop role if exists member;
                drop role if exists base;
                create role base with login;
                create role member with login;
                grant base to member;
                """
            )
            cur.execute("create database vec_priv owner base;")
    # connect as "base", create vectorizer

    pgai.install(db_url("base", "vec_priv"))
    with psycopg.connect(db_url("base", "vec_priv")) as con:
        with con.cursor() as cur:
            cur.execute(
                """
                create table blog(id bigint primary key, content text);
                select ai.create_vectorizer(
                    'blog'
                  , loading => ai.loading_column('content')
                  , destination=>ai.destination_table('base_vectorizer')
                  , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
                  , chunking=>ai.chunking_character_text_splitter(128, 10)
                  , scheduling=>ai.scheduling_none()
                  , indexing=>ai.indexing_none()
                );
                """
            )
    # connect as "member", create vectorizer
    with psycopg.connect(db_url("member", "vec_priv")) as con:
        with con.cursor() as cur:
            cur.execute("""
                  select ai.create_vectorizer(
                    'blog'
                  , loading => ai.loading_column('content')
                  , destination=> ai.destination_table('member_vectorizer')
                  , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
                  , chunking=>ai.chunking_character_text_splitter(128, 10)
                  , scheduling=>ai.scheduling_none()
                  , indexing=>ai.indexing_none()
                );
            """)
