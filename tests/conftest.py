import dotenv
import psycopg
import pytest

dotenv.load_dotenv()


def does_test_user_exist(cur: psycopg.Cursor) -> bool:
    cur.execute("""
        select count(*) > 0
        from pg_catalog.pg_roles
        where rolname = 'test'
    """)
    return cur.fetchone()[0]


def create_test_user(cur: psycopg.Cursor) -> None:
    if not does_test_user_exist(cur):
        cur.execute("create user test password 'test'")


def does_test_db_exist(cur: psycopg.Cursor) -> bool:
    cur.execute("""
        select count(*) > 0
        from pg_catalog.pg_database
        where datname = 'test'
    """)
    return cur.fetchone()[0]


def drop_test_db(cur: psycopg.Cursor) -> None:
    cur.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname = 'test'")
    cur.execute("drop database test with (force)")


def create_test_db(cur: psycopg.Cursor) -> None:
    if does_test_db_exist(cur):
        drop_test_db(cur)
    cur.execute("create database test owner test")


@pytest.fixture(scope="session", autouse=True)
def set_up_test_db() -> None:
    # create a test user and test database owned by the test user
    with psycopg.connect(f"postgres://postgres@127.0.0.1:5432/postgres", autocommit=True) as con:
        with con.cursor() as cur:
            create_test_user(cur)
            create_test_db(cur)
    # grant some things to the test user in the test database
    with psycopg.connect(f"postgres://postgres@127.0.0.1:5432/test", autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("grant execute on function pg_read_binary_file(text) to test")
            cur.execute("grant pg_read_server_files to test")
    # use the test user to create the extension in the test database
    with psycopg.connect(f"postgres://test@127.0.0.1:5432/test") as con:
        with con.cursor() as cur:
            cur.execute("create extension ai cascade")
