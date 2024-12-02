import os
import subprocess
from pathlib import Path

import psycopg
import pytest

# skip tests in this module if disabled
enable_text_to_sql_tests = os.getenv("ENABLE_TEXT_TO_SQL_TESTS")
if enable_text_to_sql_tests == "0":
    pytest.skip(allow_module_level=True)


USER = "billy"  # NOT a superuser
SRC_DB = "text_to_sql_src"
DST_DB = "text_to_sql_dst"


def db_url(user: str, dbname: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/{dbname}"


def where_am_i() -> str:
    if "WHERE_AM_I" in os.environ and os.environ["WHERE_AM_I"] == "docker":
        return "docker"
    return "host"


def docker_dir() -> str:
    return "/pgai/tests/text_to_sql"


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
            f'''-d "{db_url(USER, SRC_DB)}"''',
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
            f'''-d "{db_url(USER, DST_DB)}"''',
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
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url(USER, SRC_DB)}"''',
            "-v ON_ERROR_STOP=1",
            f"-f {docker_dir()}/init.sql",
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def read_file(filename: str) -> str:
    with open(filename, "r") as f:
        return f.read()


def extra(dbname: str) -> None:
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url(USER, dbname)}"''',
            "-v ON_ERROR_STOP=1",
            f"-f {docker_dir()}/extra.sql",
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def post_restore() -> None:
    with psycopg.connect(db_url(user=USER, dbname=DST_DB)) as con:
        with con.cursor() as cur:
            cur.execute("select ai.post_restore()")


def check_mapping() -> bool:
    with psycopg.connect(db_url(user=USER, dbname=DST_DB)) as con:
        with con.cursor() as cur:
            cur.execute("""
                select
                  count(*) =
                  count(*) filter (where (d.objtype, d.objnames, d.objargs) = (x."type", x.object_names, x.object_args))
                from ai.semantic_catalog_obj d
                cross join lateral pg_catalog.pg_identify_object_as_address
                ( d.classid
                , d.objid
                , d.objsubid
                ) x
            """)
            return cur.fetchone()[0]


def test_dump_restore():
    create_user(USER)
    create_database(SRC_DB)
    create_database(DST_DB)
    init_src()
    dump_db()
    extra(SRC_DB)  # add extra descriptions AFTER dump so snapshots match
    snapshot_db(SRC_DB)
    extra(DST_DB)  # add extra descriptions BEFORE restore to make sure that works
    restore_db()
    post_restore()
    snapshot_db(DST_DB)
    src = read_file(str(host_dir().joinpath(f"{SRC_DB}.snapshot")))
    dst = read_file(str(host_dir().joinpath(f"{DST_DB}.snapshot")))
    assert dst == src
    assert (
        check_mapping() is True
    )  # ensure that all the oids match the names after the restore
