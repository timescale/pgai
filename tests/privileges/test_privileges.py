import os
import subprocess
from pathlib import Path

import pytest

# skip tests in this module if disabled
enable_privileges_tests = os.getenv("ENABLE_PRIVILEGES_TESTS")
if not enable_privileges_tests or enable_privileges_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str, dbname: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/{dbname}"


def where_am_i() -> str:
    if "WHERE_AM_I" in os.environ and os.environ["WHERE_AM_I"] == "docker":
        return "docker"
    return "host"


def docker_dir() -> str:
    return "/pgai/tests/privileges"


def host_dir() -> Path:
    return Path(__file__).parent.absolute()


def read_file(filename: str) -> str:
    filename = Path(__file__).parent.absolute() / filename
    with open(filename, "r") as f:
        return f.read()


def psql_file(user, dbname, file: str) -> None:
    cmd = " ".join([
        "psql",
        f'''-d "{db_url(user, dbname)}"''',
        "-v ON_ERROR_STOP=1",
        "-X",
        f"-f {docker_dir()}/{file}",
    ])
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


@pytest.fixture(scope="module", autouse=True)
def init():
    psql_file("postgres", "postgres", "init0.sql")
    psql_file("alice", "privs", "init1.sql")


def run_test(kind: str) -> None:
    psql_file("postgres", "privs", f"{kind}.sql")
    expected = read_file(f"{kind}.expected")
    actual = read_file(f"{kind}.actual")
    assert actual == expected


def test_schema_privileges():
    run_test("schema")


def test_table_privileges():
    run_test("table")


def test_sequence_privileges():
    run_test("sequence")


def test_view_privileges():
    run_test("view")


def test_function_privileges():
    run_test("function")


def test_jill_privileges():
    psql_file("jill", "privs", "jill.sql")

