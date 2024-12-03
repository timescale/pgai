import os
import subprocess
from pathlib import Path

import psycopg
import pytest

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
    return "/pgai/tests/privileges"


def host_dir() -> Path:
    return Path(__file__).parent.absolute()


def read_file(filename: str) -> str:
    filename = Path(__file__).parent.absolute() / filename
    with open(filename, "r") as f:
        return f.read()


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
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


@pytest.fixture(scope="module", autouse=True)
def init():
    psql_file("postgres", "postgres", "init0.sql")
    psql_file("alice", "privs", "init1.sql")


def run_test(kind: str) -> None:
    psql_file("postgres", "privs", f"{kind}.sql")
    expected = read_file(f"{kind}.expected")
    actual = read_file(f"{kind}.actual")
    assert actual == expected


def test_schema_privileges():
    run_test("schema")


def test_table_privileges():
    run_test("table")


def test_sequence_privileges():
    run_test("sequence")


def test_view_privileges():
    run_test("view")


def test_function_privileges():
    run_test("function")


def test_jill_privileges():
    psql_file("jill", "privs", "jill.sql")


def test_secret_privileges():
    # jill cannot access any secrets
    with psycopg.connect(db_url("jill", "privs")) as con:
        with con.cursor() as cur:
            cur.execute(
                "SET ai.external_functions_executor_url='http://localhost:8000'"
            )
            with pytest.raises(Exception, match="user does not have access"):
                cur.execute("select ai.reveal_secret('OPENAI_API_KEY')")

    # jill cannot revoke from alice
    with psycopg.connect(db_url("jill", "privs")) as con:
        with con.cursor() as cur:
            with pytest.raises(Exception, match="permission denied for function"):
                cur.execute("select ai.revoke_secret('*', 'alice')")

    # jill cannot grant to alice
    with psycopg.connect(db_url("jill", "privs")) as con:
        with con.cursor() as cur:
            with pytest.raises(Exception, match="permission denied for function"):
                cur.execute("select ai.grant_secret('*', 'alice')")

    # jill cannot access ai._secrets_permissions
    with psycopg.connect(db_url("jill", "privs")) as con:
        with con.cursor() as cur:
            with pytest.raises(Exception, match="permission denied for table"):
                cur.execute("select * from ai._secret_permissions")

    # jill cannot access the env var
    with psycopg.connect(db_url("jill", "privs")) as con:
        with con.cursor() as cur:
            cur.execute(
                "SET ai.external_functions_executor_url='http://localhost:8000'"
            )
            with pytest.raises(Exception, match="user does not have access"):
                cur.execute("select ai.reveal_secret('TEST_ENV_SECRET')")

    # alice can access all the secrets and grant them to fred and joey
    with psycopg.connect(db_url("alice", "privs")) as con:
        with con.cursor() as cur:
            cur.execute(
                "SET ai.external_functions_executor_url='http://localhost:8000'"
            )
            cur.execute("select ai.reveal_secret('OPENAI_API_KEY')")
            cur.execute("select ai.reveal_secret('TEST_ENV_SECRET')")
            cur.execute("select ai.grant_secret('OPENAI_API_KEY', 'joey')")
            cur.execute("select ai.grant_secret('*', 'joey2')")
            cur.execute("select ai.grant_secret('OPENAI_API_KEY', 'fred')")

    # jill still cannot access any secrets
    with psycopg.connect(db_url("jill", "privs")) as con:
        with con.cursor() as cur:
            cur.execute(
                "SET ai.external_functions_executor_url='http://localhost:8000'"
            )
            with pytest.raises(Exception, match="user does not have access"):
                cur.execute("select ai.reveal_secret('OPENAI_API_KEY')")

    # alice can grant the secret to jill
    with psycopg.connect(db_url("alice", "privs")) as con:
        with con.cursor() as cur:
            cur.execute(
                "SET ai.external_functions_executor_url='http://localhost:8000'"
            )
            cur.execute("select ai.grant_secret('OPENAI_API_KEY', 'jill')")
            cur.execute("select ai.grant_secret('TEST_ENV_SECRET', 'jill')")

    # jill can access the secret granted to her but not the other one
    with psycopg.connect(db_url("jill", "privs")) as con:
        with con.cursor() as cur:
            cur.execute(
                "SET ai.external_functions_executor_url='http://localhost:8000'"
            )
            cur.execute("select ai.reveal_secret('OPENAI_API_KEY')")
            cur.execute("select ai.reveal_secret('TEST_ENV_SECRET')")
            with pytest.raises(Exception, match="user does not have access"):
                cur.execute("select ai.reveal_secret('OPENAI_API_KEY_2')")

    # fred cannot access any secrets even though alice granted them to him
    # because he doesn't have access to ai functions at all
    with psycopg.connect(db_url("fred", "privs")) as con:
        with con.cursor() as cur:
            cur.execute(
                "SET ai.external_functions_executor_url='http://localhost:8000'"
            )
            with pytest.raises(Exception, match="permission denied for function"):
                cur.execute("select ai.reveal_secret('OPENAI_API_KEY')")

    # alice can revoke the secret from jill
    with psycopg.connect(db_url("alice", "privs")) as con:
        with con.cursor() as cur:
            cur.execute(
                "SET ai.external_functions_executor_url='http://localhost:8000'"
            )
            cur.execute("select ai.revoke_secret('OPENAI_API_KEY', 'jill')")

    with psycopg.connect(db_url("jill", "privs")) as con:
        with con.cursor() as cur:
            cur.execute(
                "SET ai.external_functions_executor_url='http://localhost:8000'"
            )
            with pytest.raises(Exception, match="user does not have access"):
                cur.execute("select ai.reveal_secret('OPENAI_API_KEY')")

    # alice can grant the secret to all keys for jill
    with psycopg.connect(db_url("alice", "privs")) as con:
        with con.cursor() as cur:
            cur.execute(
                "SET ai.external_functions_executor_url='http://localhost:8000'"
            )
            cur.execute("select ai.grant_secret('*', 'jill')")

    # jill can access all the secrets
    with psycopg.connect(db_url("jill", "privs")) as con:
        with con.cursor() as cur:
            cur.execute(
                "SET ai.external_functions_executor_url='http://localhost:8000'"
            )
            cur.execute("select ai.reveal_secret('OPENAI_API_KEY')")
            cur.execute("select ai.reveal_secret('OPENAI_API_KEY_2')")
            cur.execute("select ai.reveal_secret('TEST_ENV_SECRET')")

    # alice can revoke the * privilege from jill
    with psycopg.connect(db_url("alice", "privs")) as con:
        with con.cursor() as cur:
            cur.execute(
                "SET ai.external_functions_executor_url='http://localhost:8000'"
            )
            cur.execute("select ai.revoke_secret('*', 'jill')")

    with psycopg.connect(db_url("jill", "privs")) as con:
        with con.cursor() as cur:
            cur.execute(
                "SET ai.external_functions_executor_url='http://localhost:8000'"
            )
            with pytest.raises(Exception, match="user does not have access"):
                cur.execute("select ai.reveal_secret('OPENAI_API_KEY')")


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
    with psycopg.connect(db_url("base", "vec_priv")) as con:
        with con.cursor() as cur:
            cur.execute(
                """
                create extension ai cascade;
                create table blog(id bigint primary key, content text);
                select ai.create_vectorizer(
                    'blog'
                  , destination=>'base_vectorizer'
                  , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
                  , chunking=>ai.chunking_character_text_splitter('content', 128, 10)
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
                  , destination=>'member_vectorizer'
                  , embedding=>ai.embedding_openai('text-embedding-3-small', 768)
                  , chunking=>ai.chunking_character_text_splitter('content', 128, 10)
                  , scheduling=>ai.scheduling_none()
                  , indexing=>ai.indexing_none()
                );
            """)
