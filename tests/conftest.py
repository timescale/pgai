import dotenv
import psycopg
import pytest

dotenv.load_dotenv()


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
    cur.execute("select ai.grant_ai_usage('test'::regrole)")


@pytest.fixture(scope="session", autouse=True)
def set_up_test_db() -> None:
    with psycopg.connect(f"postgres://postgres@127.0.0.1:5432/postgres", autocommit=True) as con:
        with con.cursor() as cursor:
            create_test_db(cursor)
    with psycopg.connect(f"postgres://postgres@127.0.0.1:5432/test") as con:
        with con.cursor() as cursor:
            create_ai_extension(cursor)
            create_test_user(cursor)


@pytest.fixture(scope="session", autouse=True)
def load_dotenv() -> None:
    dotenv.load_dotenv()
