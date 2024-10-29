import os
import subprocess
from pathlib import Path

import psycopg
import pytest

# skip tests in this module if disabled
enable_upgrade_tests = os.getenv("ENABLE_UPGRADE_TESTS")
if enable_upgrade_tests == "0":
    pytest.skip(allow_module_level=True)


USER = "marianne"  # NOT a superuser


def db_url(user: str, dbname: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/{dbname}"


def where_am_i() -> str:
    if "WHERE_AM_I" in os.environ and os.environ["WHERE_AM_I"] == "docker":
        return "docker"
    return "host"


def docker_dir() -> str:
    return "/pgai/tests/upgrade"


def host_dir() -> Path:
    return Path(__file__).parent.absolute()


def create_user() -> None:
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
                (USER,),
            )
            exists: bool = cur.fetchone()[0]
            if not exists:
                cur.execute(f"create user {USER}")  # NOT a superuser


def create_database(dbname: str) -> None:
    with psycopg.connect(
        db_url(user="postgres", dbname="postgres"), autocommit=True
    ) as con:
        with con.cursor() as cur:
            cur.execute(f"drop database if exists {dbname} with (force)")
            cur.execute(f"create database {dbname} with owner {USER}")


def fetch_versions(dbname: str) -> list[str]:
    with psycopg.connect(db_url(user=USER, dbname=dbname), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("""
            select version
            from
            (
                -- split version to major, minor, patch, and pre-release
                select version, regexp_split_to_array(version, '[.-]') as parts
                from pg_available_extension_versions
                where name = 'ai'
                and version not in ('0.1.0', '0.2.0', '0.3.0')
            ) v
            order by parts[1], parts[2], parts[3], parts[4] nulls last
            """)
            versions = []
            for row in cur.fetchall():
                versions.append(row[0])
            return versions


def create_extension(dbname: str, version: str) -> None:
    with psycopg.connect(db_url(user=USER, dbname=dbname), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute(f"create extension ai version '{version}' cascade")


def update_extension(dbname: str, version: str) -> None:
    with psycopg.connect(db_url(user=USER, dbname=dbname), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute(f"alter extension ai update to '{version}'")


def check_version(
    dbname: str,
) -> str:
    with psycopg.connect(db_url(user=USER, dbname=dbname), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("select extversion from pg_extension where extname = 'ai'")
            return cur.fetchone()[0]


def snapshot(dbname: str, name: str) -> None:
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url(USER, dbname)}"''',
            "-v ON_ERROR_STOP=1",
            "-X",
            f"-o {docker_dir()}/{name}.snapshot",
            f"-f {docker_dir()}/snapshot.sql",
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def test_upgrade():
    create_user()
    create_database("upgrade0")
    versions = fetch_versions("upgrade0")
    # start at the first version
    create_extension("upgrade0", versions[0])
    assert check_version("upgrade0") == versions[0]
    # upgrade through each version to the end
    for version in versions[1:]:
        update_extension("upgrade0", version)
        assert check_version("upgrade0") == version
    # snapshot the ai extension and schema
    snapshot("upgrade0", "upgrade0")
    # now create the extension directly at the latest
    create_database("upgrade1")
    create_extension("upgrade1", versions[-1])
    assert check_version("upgrade1") == versions[-1]
    # snapshot the ai extension and schema
    snapshot("upgrade1", "upgrade1")
    # compare the snapshots. they should match
    upgrade0 = (
        Path(__file__).parent.absolute().joinpath("upgrade0.snapshot").read_text()
    )
    upgrade1 = (
        Path(__file__).parent.absolute().joinpath("upgrade1.snapshot").read_text()
    )
    assert upgrade0 == upgrade1
