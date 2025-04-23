import os
import subprocess
from collections import namedtuple
from pathlib import Path, PosixPath

import psycopg
import pytest
import semver

from tests.conftest import detailed_notice_handler

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
    return str(
        PosixPath("/").joinpath("pgai", "projects", "extension", "tests", "upgrade")
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


def create_extension(dbname: str, version: str) -> None:
    with psycopg.connect(db_url(user=USER, dbname=dbname), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute(f"create extension ai version '{version}' cascade")


def drop_extension(dbname: str) -> None:
    with psycopg.connect(db_url(user=USER, dbname=dbname), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("drop extension ai cascade")


def update_extension(dbname: str, version: str) -> None:
    with psycopg.connect(db_url(user=USER, dbname=dbname), autocommit=True) as con:
        con.add_notice_handler(detailed_notice_handler)
        with con.cursor() as cur:
            cur.execute("SET client_min_messages TO 'debug';")
            cur.execute(f"alter extension ai update to '{version}'")


def check_version(
    dbname: str,
) -> str:
    with psycopg.connect(db_url(user=USER, dbname=dbname), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("select extversion from pg_extension where extname = 'ai'")
            return cur.fetchone()[0]


def init_db_script(dbname: str, script: str) -> None:
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url(USER, dbname)}"''',
            "-v ON_ERROR_STOP=1",
            f"-f {docker_dir()}/{script}",
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def snapshot(dbname: str, name: str, suffix: str = "") -> None:
    vacuum_vectorizer_table(dbname)
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url(USER, dbname)}"''',
            "-v ON_ERROR_STOP=1",
            "-X",
            f"-o {docker_dir()}/{name}.snapshot",
            f"-f {docker_dir()}/snapshot{suffix}.sql",
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
        # executes different init functions due to chunking function signature change.
        print("from", path.source, "to", path.target)
        init_db_script("upgrade_target", "init.sql")
        snapshot("upgrade_target", f"{path_name}-expected")
        # start at the first version in the path
        create_database("upgrade_path")
        create_extension("upgrade_path", path.path[0])
        assert check_version("upgrade_path") == path.path[0]
        init_db_script("upgrade_path", "init.sql")
        # upgrade through each version to the end
        for version in path.path[1:]:
            update_extension("upgrade_path", version)
            assert check_version("upgrade_path") == version
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


def is_version_earlier_or_equal_than(v1, v2):
    v1_parts = list(map(int, v1.split("-")[0].split(".")))
    v2_parts = list(map(int, v2.split("-")[0].split(".")))
    return v1_parts <= v2_parts


def install_pgai_library(db_url: str) -> None:
    cmd = f'pgai install -d "{db_url}"'
    if where_am_i() == "host":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def vacuum_vectorizer_table(dbname: str) -> None:
    """
    This ensures the vectorizer table is vacuumed before taking a snapshot.
    Due to addition and deletion of columns the size might otherwise differ between
    versions.
    """
    with psycopg.connect(db_url(user=USER, dbname=dbname), autocommit=True) as con:
        with con.cursor() as cur:
            # Check if the relation exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM pg_catalog.pg_class c
                    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'ai' 
                    AND c.relname = 'vectorizer'
                )
            """)
            if cur.fetchone()[0]:
                cur.execute("VACUUM FULL ai.vectorizer;")


def test_unpackaged_upgrade():
    """Test upgrading from extension to pgai library for all released versions.

    This test verifies that the vectorizer functionality can correctly transition
    from being managed by the extension to being managed by the pgai library,
    regardless of which version of the extension was previously installed.
    """
    create_user(USER)
    create_user(OTHER_USER)

    # All released versions that should be tested
    released_versions = [
        "0.10.0",
        "0.9.0",
        "0.8.0",
        "0.7.0",
        "0.6.0",
        "0.5.0",
        "0.4.1",
        "0.4.0",
    ]

    # Setup target to compare against (clean install via pgai library)
    create_database("upgrade_target")

    from ai import __version__ as latest_extension_version

    install_pgai_library(db_url(USER, "upgrade_target"))
    init_db_script("upgrade_target", "init_vectorizer_only.sql")
    snapshot("upgrade_target", "unpackaged-expected", "_vectorizer_only")
    expected_path = (
        Path(__file__).parent.absolute().joinpath("unpackaged-expected.snapshot")
    )
    expected = expected_path.read_text()

    # Test upgrading from each released version
    for version in released_versions:
        print(f"\nTesting upgrade from extension version {version} to pgai library...")

        test_db = f"upgrade_from_{version.replace('.', '_')}"
        create_database(test_db)

        # Install the old extension version
        create_extension(test_db, version)
        assert check_version(test_db) == version
        installed_lib = False
        if semver.VersionInfo.parse(version) < semver.VersionInfo.parse("0.10.0"):
            init_db_script(test_db, "init_vectorizer_only_old_api.sql")
        else:
            install_pgai_library(db_url(USER, test_db))
            installed_lib = True
            init_db_script(test_db, "init_vectorizer_only.sql")

        # Upgrade to the latest version
        if version != latest_extension_version:
            update_extension(test_db, latest_extension_version)
            assert check_version(test_db) == latest_extension_version
        else:
            print(
                f"Skipping upgrade to {latest_extension_version} because it is the latest released version"
            )

        # Drop the extension and install using pgai library
        # We are dropping the extension because we want to test the state of the vectorizer
        # library in this test. Not the extension. Dropping the extension is required to
        # ensure that the snapshots are the same on a clean install of vectorizer and the
        # extension divestment path. Also makes sure that the drop of the extension does not
        # affect the vectorizer db items.
        drop_extension(test_db)
        if not installed_lib:
            install_pgai_library(db_url(USER, test_db))

        # Snapshot and compare
        snapshot(test_db, f"unpackaged-actual-from-{version}", "_vectorizer_only")
        actual_path = (
            Path(__file__)
            .parent.absolute()
            .joinpath(f"unpackaged-actual-from-{version}.snapshot")
        )
        actual = actual_path.read_text()

        # Direct comparison of snapshots
        assert (
            actual == expected
        ), f"Snapshots do not match for upgrade from {version} at {expected_path} {actual_path}"

        print(f"Successfully upgraded from extension version {version} to pgai library")


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
            order by parts[1]::int, parts[2]::int, parts[3]::int, parts[4] nulls last
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
    init_db_script("upgrade0", "init.sql")
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
    init_db_script("upgrade1", "init.sql")
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
            update_extension("trigger_upgrade", "0.9.0")
            assert check_version("trigger_upgrade") == "0.9.0"

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
            assert version == "0.8.1"

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
