import os
import subprocess
from pathlib import Path, PosixPath

import psycopg
import pytest

import pgai

# skip tests in this module if disabled
enable_dump_restore_tests = os.getenv("ENABLE_DUMP_RESTORE_TESTS")
if enable_dump_restore_tests == "0":
    pytest.skip(allow_module_level=True)


USER = "jane"  # NOT a superuser


def db_url(user: str, dbname: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/{dbname}"


def where_am_i() -> str:
    if "WHERE_AM_I" in os.environ and os.environ["WHERE_AM_I"] == "docker":
        return "docker"
    return "host"


def docker_dir() -> str:
    return str(
        PosixPath("/").joinpath(
            "pgai", "projects", "pgai", "db", "tests", "dump_restore"
        )
    )


def host_dir() -> Path:
    return Path(__file__).parent.absolute()


def create_user(user: str) -> None:
    with psycopg.connect(
        db_url(user="postgres", dbname="postgres"), autocommit=True
    ) as con:
        with con.cursor() as cur:
            cur.execute(
                """
                select count(*) > 0
                from pg_catalog.pg_roles
                where rolname = %s
            """,
                (user,),
            )
            exists: bool = cur.fetchone()[0]
            if not exists:
                cur.execute(f"create user {user}")  # NOT a superuser


def create_database(dbname: str) -> None:
    with psycopg.connect(
        db_url(user="postgres", dbname="postgres"), autocommit=True
    ) as con:
        with con.cursor() as cur:
            cur.execute(f"drop database if exists {dbname} with (force)")
            cur.execute(f"create database {dbname} with owner {USER}")


def dump_db() -> None:
    host_dir().joinpath("dump.sql").unlink(missing_ok=True)
    cmd = " ".join(
        [
            "pg_dump -Fp --no-comments",
            f'''-d "{db_url(USER, "src")}"''',
            f"""-f {docker_dir()}/dump.sql""",
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def restore_db() -> None:
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url(USER, "dst")}"''',
            "-v VERBOSITY=verbose",
            f"-f {docker_dir()}/dump.sql",
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def snapshot_db(dbname: str) -> None:
    host_dir().joinpath(f"{dbname}.snapshot").unlink(missing_ok=True)
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url("postgres", dbname)}"''',
            "-v ON_ERROR_STOP=1",
            "-X",
            f"-o {docker_dir()}/{dbname}.snapshot",
            f"-f {docker_dir()}/snapshot.sql",
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def init_src() -> None:
    pgai.install(db_url(user=USER, dbname="src"))
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url(USER, "src")}"''',
            "-v ON_ERROR_STOP=1",
            f"-f {docker_dir()}/init.sql",
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def read_file(filename: str) -> str:
    with open(filename) as f:
        return f.read()


def after_dst() -> None:
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url(USER, "dst")}"''',
            "-v ON_ERROR_STOP=1",
            f"-f {docker_dir()}/after.sql",
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def count_vectorizers() -> int:
    with psycopg.connect(db_url(user=USER, dbname="dst"), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("select count(*) from ai.vectorizer")
            count: int = cur.fetchone()[0]
            return count


def test_dump_restore():
    create_user(USER)
    create_user("ethel")
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
    after_dst()  # make sure we can USE the restored db
    assert count_vectorizers() == 2
