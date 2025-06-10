"""Tests for upgrading between different versions of pgai database installations.

These tests verify that:
1. The pgai database can be upgraded correctly between different pypi package versions (>=0.10.0)
2. Extension upgrade paths work correctly
3. Vectorizer functionality is maintained across upgrades

The tests install old versions using pip packages, but use the source/development version
of pgai for the final upgrade and comparison. This allows testing upgrades to unreleased
changes in the development version.

Environment variables that control these tests:
- ENABLE_UPGRADE_TESTS: Set to "0" to skip all tests in this module
- FORCE_RUN_DOCKER_TESTS: Set to "1" to force tests to run even if not in Docker
- WHERE_AM_I: Set to "docker" to indicate we're running in Docker
- PGAI_TEST_VERSIONS: Comma-separated list of pgai versions to test (e.g. "0.10.0,0.10.1")
- PGAI_TARGET_VERSION: Target version to upgrade to (defaults to current source version)
"""

import os
import subprocess
from collections import namedtuple
from pathlib import Path, PosixPath

import psycopg
import pytest

# skip tests in this module if disabled
enable_upgrade_tests = os.getenv("ENABLE_UPGRADE_TESTS")
if enable_upgrade_tests == "0":
    pytest.skip(allow_module_level=True)


USER = "marianne"  # NOT a superuser
OTHER_USER = "vera"  # NOT a superuser


def db_url(user: str, dbname: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/{dbname}"


def where_am_i() -> str:
    """Determine if we're running in Docker or on the host.
    
    This can be controlled by setting the WHERE_AM_I environment variable to 'docker'.
    Otherwise, it tries to detect whether we're running inside a container.
    """
    if "WHERE_AM_I" in os.environ:
        return os.environ["WHERE_AM_I"]
    
    # Try to detect if we're running in Docker
    try:
        with open('/proc/1/cgroup', 'r') as f:
            if 'docker' in f.read():
                return "docker"
    except:
        pass
    
    # Check for .dockerenv file
    if os.path.exists('/.dockerenv'):
        return "docker"
    
    return "host"


def requires_docker(func):
    """Decorator to skip tests that require Docker when not running in Docker."""
    def wrapper(*args, **kwargs):
        if where_am_i() != "docker":
            if os.getenv("FORCE_RUN_DOCKER_TESTS") != "1":
                pytest.skip("Test requires Docker environment")
        return func(*args, **kwargs)
    return wrapper


def docker_dir() -> str:
    return str(
        PosixPath("/").joinpath("pgai", "projects", "pgai", "db", "tests", "upgrade")
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


def check_version(
    dbname: str,
) -> str:
    with psycopg.connect(db_url(user=USER, dbname=dbname), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("select version from ai.pgai_lib_version where name = 'ai'")
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
        cmd = f"docker exec -w {docker_dir()} pgai-db {cmd}"
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
        cmd = f"docker exec -w {docker_dir()} pgai-db {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


# @requires_docker
def test_upgrades():
    """Test upgrading pgai database installation across different pypy pgai package versions.

        This test verifies that the database created by `pgai install -d <db_url>` can be
        upgraded correctly when moving between different package versions (>=0.10.0).
        """
    create_user(USER)
    create_user(OTHER_USER)

    # All released pgai versions that should be tested (>=0.10.0)
    # We use a list of versions in descending order to test upgrading from older to newer
    # TODO: automate
    released_versions = [
        # "0.10.0",
        # "0.10.1",
        # "0.10.2",
        # "0.10.3",
        "0.10.4",
    ]

    # Setup target to compare against (clean install via current pgai library from source)
    create_database("upgrade_target")
    db = db_url(USER, "upgrade_target")
    # install local development version
    install_pgai_db(db, "")

    from pgai import __version__ as current_dev_version
    assert check_version("upgrade_target") == current_dev_version

    init_db_script("upgrade_target", "init.sql")
    snapshot("upgrade_target", "expected")
    expected = (
        Path(__file__).parent.absolute().joinpath("expected.snapshot").read_text()
    )

    # Test upgrading from each released version
    for version in released_versions:
        print(f"\nTesting upgrade from pgai version {version} to the latest (from actual source code)...")

        create_database("upgrade_source")
        install_pgai_db(db, version)
        assert check_version("upgrade_source") == version

        init_db_script("upgrade_target", "init.sql")


        # executes different init functions due to chunking function signature change.
        # print("from", path.source, "to", path.target)
        init_db_script("upgrade_source", "init.sql")
        version_slug = version.replace('.', '_')
        snapshot("upgrade_source", f"{version_slug}-actual")
        ###############################
        ############################
        ###########################
        ######## VOY POR AQUI
        ############################
        ###########################
        ############################
        # start at the first version in the path


        # compare the snapshots. they should match
        actual = (
            Path(__file__)
            .parent.absolute()
            .joinpath(f"{version_slug}-actual.snapshot")
            .read_text()
        )

        debug_path = (
            Path(__file__).parent.absolute().joinpath(f"{version_slug}-actual.snapshot")
        )
        assert actual == expected, f"snapshots do not match for {debug_path}"


def is_version_earlier_or_equal_than(v1, v2):
    v1_parts = list(map(int, v1.split("-")[0].split(".")))
    v2_parts = list(map(int, v2.split("-")[0].split(".")))
    return v1_parts <= v2_parts


def install_pgai_db(db_url: str, version: str = "") -> None:
    """Install the pgai db into the database.
    
    Args:
        db_url: Database connection URL
        version: If provided, use pgai on the specified version to install the db.
                If empty, use the local source version instead.
    """
    if version == "":
        # Use local development version
        source_root = Path(__file__).parents[4].absolute()  # Go up 4 directories to the workspace root
        cmd = f'uv run pgai install --strict -d "{db_url}"'
        if where_am_i() == "docker":
            subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(source_root))
        else:
            cmd = f"docker exec -w {docker_dir()} -e PYTHONPATH={source_root} pgai-db {cmd}"
            subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))
    else:
        # Use pip-installed version
        cmd = f'uvx pgai@0.10.0 install -d "{db_url}"'
        if where_am_i() == "docker":
            subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))
        else:
            cmd = f"docker exec -w {docker_dir()} pgai-db {cmd}"
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


def check_pgai_lib_version(dbname: str) -> str:
    """Check the pgai library version in the database.
    """
    with psycopg.connect(db_url(user=USER, dbname=dbname), autocommit=True) as con:
        with con.cursor() as cur:
            # Try the current version table schema first
            cur.execute("SELECT version FROM ai.pgai_lib_version")
            return cur.fetchone()[0]
