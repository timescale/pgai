import os
import subprocess
from pathlib import Path

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


def init() -> None:
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url("postgres", "postgres")}"''',
            "-v ON_ERROR_STOP=1",
            "-X",
            f"-f {docker_dir()}/init.sql",
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    result = subprocess.run(
        cmd,
        check=True,
        shell=True,
        env=os.environ,
        cwd=str(host_dir()),
        text=True,
        capture_output=True,
    )
    return result.stdout


def test_contents(snapshot) -> None:
    output = init()
    assert output == snapshot
