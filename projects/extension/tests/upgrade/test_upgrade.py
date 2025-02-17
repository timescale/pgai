import os
import subprocess
from collections import namedtuple
from pathlib import Path

import psycopg
import pytest

# skip tests in this module if disabled
enable_upgrade_tests = os.getenv("ENABLE_UPGRADE_TESTS")
if enable_upgrade_tests == "0":
    pytest.skip(allow_module_level=True)


USER = "marianne"  # NOT a superuser
OTHER_USER = "vera"  # NOT a superuser


UpgradePath = namedtuple("UpgradePath", ["source", "target", "path"])


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


def init(dbname: str) -> None:
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url(USER, dbname)}"''',
            "-v ON_ERROR_STOP=1",
            f"-f {docker_dir()}/init.sql",
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


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


def fetch_upgrade_paths(dbname: str) -> list[UpgradePath]:
    with psycopg.connect(db_url(user=USER, dbname=dbname), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("""
            select source, target, regexp_split_to_array(path, '--')
            from pg_catalog.pg_extension_update_paths('ai')
            where path is not null
            """)
            paths: list[UpgradePath] = []
            for row in cur.fetchall():
                paths.append(UpgradePath(row[0], row[1], row[2]))
            return paths


def test_upgrades():
    create_user(USER)
    create_user(OTHER_USER)
    paths = fetch_upgrade_paths("postgres")
    for path in paths:
        path_name = "--".join(path.path)
        # create the extension directly at the target version
        create_database("upgrade_target")
        create_extension("upgrade_target", path.target)
        assert check_version("upgrade_target") == path.target
        init("upgrade_target")
        # Test that the trigger function exists
        # After each case, add:
        with psycopg.connect(db_url(user=USER, dbname="upgrade_target"), autocommit=True) as con:
            with con.cursor() as cur:
                # Check if function exists and get its properties
                cur.execute("""
                    SELECT n.nspname, p.proname, p.proowner::regrole, 
                           p.proacl, p.prokind
                    FROM pg_proc p
                    JOIN pg_namespace n ON p.pronamespace = n.oid
                    WHERE p.proname = '_vectorizer_src_trg_1'
                """)
                print(f"Function details in upgrade_target:", cur.fetchone())
        snapshot("upgrade_target", f"{path_name}-expected")
        # start at the first version in the path
        create_database("upgrade_path")
        create_extension("upgrade_path", path.path[0])
        assert check_version("upgrade_path") == path.path[0]
        init("upgrade_path")
        # upgrade through each version to the end
        for version in path.path[1:]:
            update_extension("upgrade_path", version)
            assert check_version("upgrade_path") == version
        # Test that the trigger function exists
        # After each case, add:
        with psycopg.connect(db_url(user=USER, dbname="upgrade_path"), autocommit=True) as con:
            with con.cursor() as cur:
                # Check if function exists and get its properties
                cur.execute("""
                    SELECT n.nspname, p.proname, p.proowner::regrole, 
                           p.proacl, p.prokind
                    FROM pg_proc p
                    JOIN pg_namespace n ON p.pronamespace = n.oid
                    WHERE p.proname = '_vectorizer_src_trg_1'
                """)
                print(f"Function details in upgrade_path:", cur.fetchone())
        snapshot("upgrade_path", f"{path_name}-actual")
        # compare the snapshots. they should match
        expected = (
            Path(__file__)
            .parent.absolute()
            .joinpath(f"{path_name}-expected.snapshot")
            .read_text()
        )
        actual = (
            Path(__file__)
            .parent.absolute()
            .joinpath(f"{path_name}-actual.snapshot")
            .read_text()
        )

        debug_path = (
            Path(__file__).parent.absolute().joinpath(f"{path_name}-actual.snapshot")
        )
        assert actual == expected, f"snapshots do not match for {debug_path}"


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
            ) v
            where parts[4] is null -- ignore versions with a prerelease tag
            order by parts[1], parts[2], parts[3], parts[4] nulls last
            """)
            versions = []
            for row in cur.fetchall():
                versions.append(row[0])
            return versions


def test_production_version_upgrade_path():
    create_user(USER)
    create_user(OTHER_USER)
    create_database("upgrade0")
    versions = fetch_versions("upgrade0")
    # start at the first version
    create_extension("upgrade0", versions[0])
    assert check_version("upgrade0") == versions[0]
    init("upgrade0")
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
    init("upgrade1")
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


def test_vectorizer_trigger_upgrade():
    create_user(USER)
    create_user(OTHER_USER)
    create_database("trigger_upgrade")

    # Create extension at 0.8.0
    create_extension("trigger_upgrade", "0.8.0")
    assert check_version("trigger_upgrade") == "0.8.0"

    # Create a test table and vectorizer
    with psycopg.connect(
        db_url(user=USER, dbname="trigger_upgrade"), autocommit=True
    ) as con:
        with con.cursor() as cur:
            # Create test table
            cur.execute("""
                CREATE TABLE public.upgrade_test (
                    id int primary key,
                    content text not null
                )
            """)

            # Create vectorizer
            cur.execute("""
                SELECT ai.create_vectorizer(
                    'public.upgrade_test'::regclass,
                    embedding=>ai.embedding_openai('text-embedding-3-small', 768),
                    chunking=>ai.chunking_character_text_splitter('content'),
                    scheduling=>ai.scheduling_none()
                )
            """)
            vectorizer_id = cur.fetchone()[0]

            # Get the trigger function definition before upgrade
            cur.execute(
                """
                SELECT p.prosrc 
                FROM pg_proc p
                JOIN pg_trigger t ON t.tgfoid = p.oid
                JOIN pg_class c ON t.tgrelid = c.oid
                JOIN ai.vectorizer v ON v.trigger_name = t.tgname
                WHERE v.id = %s
            """,
                (vectorizer_id,),
            )
            old_trigger_def = cur.fetchone()[0]

            # Verify old trigger doesn't handle PK changes
            assert "IS DISTINCT FROM" not in old_trigger_def

            # Upgrade to the new version
            update_extension("trigger_upgrade", "0.8.1-dev")
            assert check_version("trigger_upgrade") == "0.8.1-dev"

            # Get the new trigger function definition
            cur.execute(
                """
                SELECT p.prosrc 
                FROM pg_proc p
                JOIN pg_trigger t ON t.tgfoid = p.oid
                JOIN pg_class c ON t.tgrelid = c.oid
                JOIN ai.vectorizer v ON v.trigger_name = t.tgname
                WHERE v.id = %s
            """,
                (vectorizer_id,),
            )
            new_trigger_def = cur.fetchone()[0]

            # Verify new trigger has the PK change handling
            assert "IS DISTINCT FROM" in new_trigger_def

            # Check that the version in the config was updated
            cur.execute(
                """
                SELECT config->>'version'
                FROM ai.vectorizer
                WHERE id = %s
            """,
                (vectorizer_id,),
            )
            version = cur.fetchone()[0]
            assert version == "0.9.0"

            # Test trigger functionality
            # Insert a row
            cur.execute("INSERT INTO public.upgrade_test VALUES (1, 'test content')")

            # Verify row was queued
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM ai._vectorizer_q_1 
                    WHERE id = 1
                )
            """)
            assert cur.fetchone()[0]

            # Update with PK change
            cur.execute("UPDATE public.upgrade_test SET id = 2 WHERE id = 1")

            # Verify old row was deleted from target and new PK was queued
            cur.execute("""
                SELECT NOT EXISTS (
                    SELECT 1 
                    FROM upgrade_test_embedding_store 
                    WHERE id = 1
                )
                AND EXISTS (
                    SELECT 1 
                    FROM ai._vectorizer_q_1 
                    WHERE id = 2
                )
            """)
            assert cur.fetchone()[0]
