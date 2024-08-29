import os
import subprocess
from pathlib import Path

import psycopg
import pytest

# skip tests in this module if disabled
enable_dump_restore_tests = os.getenv("ENABLE_DUMP_RESTORE_TESTS")
if not enable_dump_restore_tests or enable_dump_restore_tests == "0":
    pytest.skip(allow_module_level=True)


USER = "jane"  # NOT a superuser


def db_url(user: str, dbname: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/{dbname}"


def where_am_i() -> str:
    if "WHERE_AM_I" in os.environ and os.environ["WHERE_AM_I"] == "docker":
        return "docker"
    return "host"


def docker_dir() -> str:
    return "/pgai/tests/dump_restore"


def host_dir() -> Path:
    return Path(__file__).parent.absolute()


def create_user() -> None:
    with psycopg.connect(db_url(user="postgres", dbname="postgres"), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("""
                select count(*) > 0
                from pg_catalog.pg_roles
                where rolname = %s
            """, (USER,))
            exists: bool = cur.fetchone()[0]
            if not exists:
                cur.execute(f"create user {USER}")  # NOT a superuser


def does_db_exist(cur: psycopg.Cursor, dbname: str) -> bool:
    cur.execute("""
        select count(*) > 0
        from pg_catalog.pg_database
        where datname = %s
    """, (dbname,))
    return cur.fetchone()[0]


def drop_db(cur: psycopg.Cursor, dbname: str) -> None:
    cur.execute(f"drop database {dbname} with (force)")


def create_database(dbname: str) -> None:
    with psycopg.connect(db_url(user="postgres", dbname="postgres"), autocommit=True) as con:
        with con.cursor() as cur:
            if does_db_exist(cur, dbname):
                drop_db(cur, dbname)
            cur.execute(f"create database {dbname} with owner {USER}")


def dump_db() -> None:
    host_dir().joinpath("dump.sql").unlink(missing_ok=True)
    cmd = " ".join([
        "pg_dump -Fp",
        f'''-d "{db_url(USER, "src")}"''',
        f'''-f {docker_dir()}/dump.sql'''
    ])
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def restore_db() -> None:
    with psycopg.connect(db_url(user=USER, dbname="dst")) as con:
        with con.cursor() as cur:
            cur.execute(f"create extension ai cascade")
    cmd = " ".join([
        "psql",
        f'''-d "{db_url(USER, "dst")}"''',
        "-v VERBOSITY=verbose",
        f"-f {docker_dir()}/dump.sql",
    ])
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def snapshot_db(dbname: str) -> None:
    host_dir().joinpath(f"{dbname}.snapshot").unlink(missing_ok=True)
    cmd = " ".join([
        "psql",
        f'''-d "{db_url("postgres", dbname)}"''',
        "-v ON_ERROR_STOP=1",
        f"-o {docker_dir()}/{dbname}.snapshot",
        f"-f {docker_dir()}/snapshot.sql",
    ])
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def init_src() -> None:
    cmd = " ".join([
        "psql",
        f'''-d "{db_url(USER, "src")}"''',
        "-v ON_ERROR_STOP=1",
        f"-f {docker_dir()}/init.sql",
    ])
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def read_file(filename: str) -> str:
    with open(filename, "r") as f:
        return f.read()


def test_dump_restore():
    create_user()
    create_database("src")
    create_database("dst")
    init_src()
    snapshot_db("src")
    dump_db()
    restore_db()
    snapshot_db("dst")
    src = read_file(str(host_dir().joinpath("src.snapshot")))
    dst = read_file(str(host_dir().joinpath("dst.snapshot")))
    assert dst == src



