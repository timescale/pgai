import os

import dotenv
import psycopg
import pytest

dotenv.load_dotenv()


def is_running_in_docker() -> bool:
    where_am_i = os.getenv("WHERE_AM_I")
    return True if where_am_i and where_am_i == "docker" else False


def db_host_port() -> str:
    if is_running_in_docker():
        return "localhost:5432"
    else:
        return "127.0.0.1:9876"


def does_test_db_exist(cur: psycopg.Cursor) -> bool:
    cur.execute("""
        select count(*) > 0
        from pg_catalog.pg_database
        where datname = 'test'
    """)
    return cur.fetchone()[0]


def drop_test_db(cur: psycopg.Cursor) -> None:
    cur.execute("drop database test")


def create_test_db(cur: psycopg.Cursor) -> None:
    if does_test_db_exist(cur):
        drop_test_db(cur)
    cur.execute("create database test")


def does_test_user_exist(cur: psycopg.Cursor) -> bool:
    cur.execute("""
        select count(*) > 0
        from pg_catalog.pg_roles
        where rolname = 'test'
    """)
    return cur.fetchone()[0]


def create_ai_extension(cur: psycopg.Cursor) -> None:
    cur.execute("create extension ai cascade")


def create_test_user(cur: psycopg.Cursor) -> None:
    if not does_test_user_exist(cur):
        cur.execute("create user test password 'test'")
    cur.execute("grant create on schema public to test")
    cur.execute("grant execute on function pg_read_binary_file(text) to test")
    cur.execute("grant pg_read_server_files to test")
    cur.execute("grant usage on schema ai to test")


@pytest.fixture(scope="session", autouse=True)
def set_up_test_db() -> None:
    with psycopg.connect(
        f"postgres://postgres@{db_host_port()}/postgres", autocommit=True
    ) as con:
        with con.cursor() as cur:
            create_test_db(cur)
    with psycopg.connect(f"postgres://postgres@{db_host_port()}/test") as con:
        with con.cursor() as cur:
            create_ai_extension(cur)
            create_test_user(cur)


@pytest.fixture()
def db_url() -> str:
    return f"postgres://test:test@{db_host_port()}/test"


@pytest.fixture(scope="session", autouse=True)
def load_dotenv() -> None:
    dotenv.load_dotenv()
