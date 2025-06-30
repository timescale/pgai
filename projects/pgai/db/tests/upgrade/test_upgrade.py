"""Tests for upgrading between different versions of pgai database installations.

OVERVIEW:
These tests verify that pgai can be successfully upgraded from any released version
to the current development version, ensuring backward compatibility and data integrity.

HOW UPGRADE TESTING WORKS:
The test strategy uses a "snapshot comparison" approach:

1. CREATE EXPECTED STATE: Install the current development version fresh in a new database
   and create a snapshot of the resulting database state.

2. CREATE ACTUAL STATE: Start with an old version, upgrade it to the current development
   version, and create a snapshot of the upgraded database.

3. COMPARE SNAPSHOTS: The two snapshots must be identical for the test to pass.

UPGRADE PROCESS:
When pgai is "installed" on a database that already has pgai, it automatically performs
an upgrade by:
1. Checking the current version in ai.pgai_lib_version table
2. Running any migration scripts needed to reach the target version (incremental scripts)
3. Recording applied migrations in ai.pgai_lib_migration table
4. Updating the version number

SNAPSHOT GENERATION:
Snapshots capture the complete database state including:
- All objects in the 'ai' schema (tables, functions, views, indexes, permissions)
- Function definitions and bodies
- Migration history (with version-agnostic hashing)
- Test data in the 'wiki' schema

HACKS AND WORKAROUNDS:
Several hacks are needed to ensure reliable snapshot comparison:

1. VERSION STRING REPLACEMENT: Migration bodies may contain version-specific strings (__version__ placeholders replaced by the build.py).
   We normalize these by replacing source version strings with target version strings.

2. MIGRATION EXCLUSION: Some migrations had bugs that were later fixed. We exclude
   these problematic migrations from snapshot comparison using the exclude_incrementals
   parameter since migrations are never applied twice.

3. VACUUM BEFORE SNAPSHOT: The vectorizer table undergoes schema changes between
   versions. We vacuum it to ensure consistent physical layout between databases
   with identical logical content.

4. FIXUP SCRIPTS: Post-upgrade SQL scripts that clean up leftovers and differences
   that remain after the upgrade process. These handle cases where upgrades don't
   perfectly replicate the state of a fresh installation (i.e. upgrades not removing those leftovers).

WHEN FIXUPS ARE NEEDED:
Fixups are required when:
- A migration introduced a bug that was later fixed in subsequent versions
- Upgrades leave behind artifacts, incorrect permissions, or other leftovers
- The upgraded database state doesn't perfectly match a fresh installation because of a known issue
- Objects need to be recreated to match the current expected state
- Example: versions 0.10.4 and 0.10.5 had incorrect permissions on vectorizer_errors view
  that needed manual correction after upgrade

Environment variables that control these tests:
- ENABLE_UPGRADE_TESTS: Set to "0" to skip all tests in this module
- WHERE_AM_I: Set to "docker" to indicate we're running in Docker, "host" otherwise
"""

import concurrent.futures
import os
import subprocess
from pathlib import Path, PosixPath

import psycopg
import pytest

from pgai import __version__ as current_dev_version

# skip tests in this module if disabled
enable_upgrade_tests = os.getenv("ENABLE_UPGRADE_TESTS")
if enable_upgrade_tests == "0":
    pytest.skip(allow_module_level=True)


USER = "ona"  # NOT a superuser
OTHER_USER = "arlet"  # NOT a superuser


def test_upgrades():
    """Test upgrading from multiple released versions to the current development version.

    This test verifies that pgai can be successfully upgraded from each released version
    to the current development version, and that the resulting database state matches
    what we get from a fresh installation of the development version.

    The test runs upgrades from multiple versions in parallel for efficiency.
    """
    create_user(USER)
    create_user(OTHER_USER)

    # List of released versions to test upgrades from, with their required fixups
    # Format: (version, exclude_migration_files, fixup_scripts)
    # - exclude_migration_files: Migration files to exclude from snapshot comparison
    #   (used when a migration was buggy and later fixed)
    # - fixup_scripts: SQL scripts to run after upgrade to fix known issues
    released_versions = [
        # ("0.10.0", [], []), # TODO Uncomment when fixed. See https://github.com/timescale/pgai/issues/835
        # ("0.10.1", [], []), # TODO Uncomment when fixed. See https://github.com/timescale/pgai/issues/835
        ("0.10.2", [], []),
        ("0.10.3", [], []),
        (
            # Bug introduced in 0.10.4, fixed in 0.11.0
            "0.10.4",
            ["030-add_vectorizer_errors_view.sql"],
            ["revoke_vectorizer_errors_privileges.sql"],
        ),
        (
            # Bug introduced in 0.10.4, fixed in 0.11.0
            "0.10.5",
            ["030-add_vectorizer_errors_view.sql"],
            ["revoke_vectorizer_errors_privileges.sql"],
        ),
        ("0.11.0", [], []),
        ("0.11.1", [], []),
        ("0.11.2", [], []),
    ]

    # Run all upgrade tests in parallel for efficiency
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                upgrade_and_compare, version, current_dev_version, exclude, fixups
            )
            for version, exclude, fixups in released_versions
        ]
        for future in concurrent.futures.as_completed(futures):
            future.result()  # will raise exception if any test fails


def upgrade_and_compare(from_version, to_version, exclude_incrementals, fixups):
    """Test upgrading from a specific version to the current development version.

    This function implements the core upgrade testing logic by:
    1. Creating a "target" database with a fresh install of the current dev version
    2. Creating a "source" database with the old version, then upgrading it
    3. Comparing database snapshots to ensure they match

    Args:
        from_version: The source version to upgrade from (e.g., "0.10.2")
        to_version: The target version to upgrade to
        exclude_incrementals: Migration files to exclude from snapshot comparison
        fixups: Post-upgrade fixup scripts to apply to the source database prior to snapshotting
    """
    target_version_slug = to_version.replace(".", "_")
    source_version_slug = from_version.replace(".", "_")
    target_database_name = f"upgrade_target_{source_version_slug}_{target_version_slug}"

    # STEP 1: Create the "expected" database state by installing the current dev version fresh
    # This represents what the database should look like after a successful upgrade
    create_database(target_database_name)
    install_pgai_db(target_database_name, to_version)
    assert check_version(target_database_name) == to_version
    init_db_script(target_database_name, "init.sql")  # Create test data and vectorizer

    # Generate the "expected" snapshot that the upgraded database should match
    expected_snapshot_filename = (
        f"{source_version_slug}-{target_version_slug}-expected.snapshot"
    )
    snapshot(
        target_database_name,
        expected_snapshot_filename,
        from_version,
        exclude_incrementals,
    )

    # STEP 2: Create the "actual" database by upgrading from the old version
    # This simulates a real upgrade scenario
    source_database_name = f"source_{source_version_slug}"
    create_database(source_database_name)

    # Install the old version first
    install_pgai_db(source_database_name, from_version)
    assert check_version(source_database_name) == from_version

    # Set up test data with the old version
    init_db_script(source_database_name, "init.sql")

    # Perform the upgrade to the current dev version
    install_pgai_db(source_database_name, to_version)
    assert check_version(source_database_name) == to_version

    # Apply any necessary fixups for this version
    # Fixups clean up leftovers and differences that remain after upgrade,
    # ensuring the upgraded database matches the state of a fresh installation
    for fixup in fixups:
        fixup_path = Path(__file__).parent.absolute().joinpath("fixups", fixup)
        if fixup_path.exists():
            init_db_script(source_database_name, f"fixups/{fixup}")

    # Generate the "actual" snapshot of the upgraded database
    actual_snapshot_filename = f"{source_version_slug}-actual.snapshot"
    snapshot(
        source_database_name,
        actual_snapshot_filename,
        from_version,
        exclude_incrementals,
    )

    # STEP 3: Compare snapshots to verify the upgrade worked correctly
    # The snapshots must be identical for the test to pass
    actual = Path(__file__).parent.absolute().joinpath(actual_snapshot_filename)
    expected = Path(__file__).parent.absolute().joinpath(expected_snapshot_filename)

    assert (
        actual.read_text() == expected.read_text()
    ), f"snapshots do not match for {actual}"


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
        with open("/proc/1/cgroup") as f:
            if "docker" in f.read():
                return "docker"
    except (OSError, FileNotFoundError):
        pass

    # Check for .dockerenv file
    if os.path.exists("/.dockerenv"):
        return "docker"

    return "host"


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


def snapshot(
    dbname: str, filename: str, source_version, exclude_migration_files: list[str]
) -> None:
    """Generate a database snapshot for comparison purposes.

    This function creates a comprehensive snapshot of the database state including:
    - All objects in the 'ai' schema (tables, functions, views, etc.)
    - Function definitions and permissions
    - Migration history (with version string normalization)
    - Test data in the 'wiki' schema

    The snapshot is designed to be reproducible and comparable between different
    database instances, with several hacks to ensure consistency:

    1. Version string replacement: Source version strings in migration bodies are
       replaced with target version strings to handle version-specific content
    2. Migration exclusion: Buggy migrations can be excluded from comparison
    3. Vacuum before snapshot: Ensures consistent table sizes
    4. MD5 hashing of migration bodies: Handles whitespace differences

    Args:
        dbname: Name of the database to snapshot
        filename: Output filename for the snapshot
        source_version: Original version (for string replacement)
        exclude_migration_files: List of migration files to exclude from comparison
    """
    # Vacuum the vectorizer table to ensure consistent state between snapshots
    # This is necessary because column additions/deletions can cause size differences
    vacuum_vectorizer_table(dbname)

    # Prepare the list of migration files to exclude from snapshot comparison
    # This is used when certain migrations had bugs that were later fixed
    exclude_sql = ", ".join(
        f"'{f}'" for f in exclude_migration_files
    )  # quoted and comma-separated

    cmd_parts = [
        "psql",
        f'''-d "{db_url(USER, dbname)}"''',
        "-v ON_ERROR_STOP=1",
        "-X",  # Don't read ~/.psqlrc
        # HACK: Replace source version strings with target version in migration bodies
        # This handles cases where migration content references specific versions
        f'-v source_version="{source_version}"',
        f'-v target_version="{current_dev_version}"',
        # HACK: Inject the exclude list to filter out problematic migrations
        f'-v exclude_list="{exclude_sql or "NULL"}"',
        f"-f {docker_dir()}/snapshot.sql",  # SQL script that generates the snapshot
        f"-o {docker_dir()}/{filename}",  # Output file
    ]
    cmd = " ".join(cmd_parts)

    # Execute either directly in Docker or via docker exec from host
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-db {cmd}"

    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def is_version_earlier_or_equal_than(v1, v2):
    v1_parts = list(map(int, v1.split("-")[0].split(".")))
    v2_parts = list(map(int, v2.split("-")[0].split(".")))
    return v1_parts <= v2_parts


def install_pgai_db(dbname: str, version: str) -> None:
    """Install or upgrade pgai in the database.

    This function handles both fresh installations and upgrades by calling the
    'pgai install' command. The pgai install command automatically detects if
    pgai is already installed and performs an upgrade if necessary.

    Args:
        dbname: Name of the database to install/upgrade pgai in
        version: If provided, install from PyPI package at this version.
                If empty string, use the local development version.
    """

    db = db_url(user=USER, dbname=dbname)
    if version == current_dev_version:
        # Use local development version (from source code)
        source_root = (
            Path(__file__).parents[4].absolute()
        )  # Go up 4 directories to the workspace root
        cmd = f'uv run pgai install --strict -d "{db}"'
        if where_am_i() == "docker":
            subprocess.run(
                cmd, check=True, shell=True, env=os.environ, cwd=str(source_root)
            )
        else:
            cmd = f"docker exec -w {docker_dir()} -e PYTHONPATH={source_root} pgai-db {cmd}"
            subprocess.run(
                cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir())
            )
    else:
        # Use specific PyPI package version
        # HACK: Setting UV_PROJECT_ENVIRONMENT to avoid using the local dev venv outside CI
        # This ensures we get a clean environment with the specified pgai version
        env = os.environ.copy()
        if not os.getenv("CI"):
            env["UV_PROJECT_ENVIRONMENT"] = f"/tmp/uv_venv/{version}"

        # HACK: --no-build-package pymupdf to avoid building pymupdf from source
        # This speeds up the installation and avoids potential build issues
        cmd = f'uvx --no-build-package pymupdf pgai@{version} install -d "{db}"'
        if where_am_i() == "docker":
            subprocess.run(cmd, check=True, shell=True, env=env, cwd=str(host_dir()))
        else:
            cmd = f"docker exec -w {docker_dir()} pgai-db {cmd}"
            subprocess.run(cmd, check=True, shell=True, env=env, cwd=str(host_dir()))


def vacuum_vectorizer_table(dbname: str) -> None:
    """Vacuum the vectorizer table to ensure consistent snapshots.

    HACK: This is necessary because the vectorizer table undergoes schema changes
    (column additions/deletions) between versions. Without vacuuming, the physical
    size of the table can differ between an upgraded database and a fresh install,
    even when the logical content is identical.

    VACUUM FULL reclaims all unused space and rebuilds the table, ensuring that
    databases with identical logical content have identical physical layout.

    Args:
        dbname: Name of the database to vacuum the vectorizer table in.
    """
    with psycopg.connect(db_url(user=USER, dbname=dbname), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("VACUUM FULL ai.vectorizer;")


def check_version(dbname: str) -> str:
    """Check the pgai library version in the database."""
    with psycopg.connect(db_url(user=USER, dbname=dbname), autocommit=True) as con:
        with con.cursor() as cur:
            # Try the current version table schema first
            cur.execute("SELECT version FROM ai.pgai_lib_version")
            return cur.fetchone()[0]
