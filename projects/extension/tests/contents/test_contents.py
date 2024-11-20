import os
import subprocess
from pathlib import Path

import psycopg
import pytest


# skip tests in this module if disabled
enable_contents_tests = os.getenv("ENABLE_CONTENTS_TESTS")
if enable_contents_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str, dbname: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/{dbname}"


def where_am_i() -> str:
    if "WHERE_AM_I" in os.environ and os.environ["WHERE_AM_I"] == "docker":
        return "docker"
    return "host"


def docker_dir() -> str:
    return "/pgai/tests/contents"


def host_dir() -> Path:
    return Path(__file__).parent.absolute()


def init(version: int) -> None:
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url("postgres", "postgres")}"''',
            "-v ON_ERROR_STOP=1",
            "-X",
            f"-o {docker_dir()}/output{version}.actual",
            f"-f {docker_dir()}/init.sql",
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def major_version() -> int:
    with psycopg.connect(
        db_url(user="postgres", dbname="postgres"), autocommit=True
    ) as con:
        with con.cursor() as cur:
            cur.execute("show server_version_num")
            version = cur.fetchone()[0]
            return int(version[0:2])


def test_contents() -> None:
    version = major_version()
    init(version)
    actual = host_dir().joinpath(f"output{version}.actual").read_text()
    expected = host_dir().joinpath(f"output{version}.expected").read_text()
    assert actual == expected
