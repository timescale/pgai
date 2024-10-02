import os
import subprocess
from pathlib import Path

import psycopg
import pytest

# skip tests in this module if disabled
enable_vectorizer_tool_tests = os.getenv("ENABLE_VECTORIZER_TOOL_TESTS")
if not enable_vectorizer_tool_tests or enable_vectorizer_tool_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str, dbname: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/{dbname}"


def create_database(dbname: str) -> None:
    with psycopg.connect(db_url(user="postgres", dbname="postgres"), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute(f"drop database if exists {dbname} with (force)")
            cur.execute(f"create database {dbname}")


def vectorizer_src_dir() -> Path:
    p = (Path(__file__)
         .parent  # vectorizer_tool
         .parent  # tests
         .parent  # project root
         .joinpath("src", "vectorizer").resolve())
    return p


def test_bad_db_url():
    env = os.environ.copy()
    env["VECTORIZER_DB_URL"] = db_url("postgres", "this_is_not_a_db")
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run("python3 -m vectorizer",
                       shell=True,
                       check=True,
                       text=True,
                       capture_output=True,
                       env=env,
                       cwd=vectorizer_src_dir(),
                       )
    env.pop("VECTORIZER_DB_URL")
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(f"python3 -m vectorizer -d '{db_url('postgres', 'cli')}'",
                       shell=True,
                       check=True,
                       text=True,
                       capture_output=True,
                       env=env,
                       cwd=vectorizer_src_dir(),
                       )


def test_pgai_not_installed():
    create_database("cli")
    env = os.environ.copy()
    env["VECTORIZER_DB_URL"] = db_url("postgres", "cli")
    p = subprocess.run("python3 -m vectorizer",
                       shell=True,
                       capture_output=True,
                       text=True,
                       env=env,
                       cwd=vectorizer_src_dir(),
                       )
    assert p.returncode == 1
    assert str(p.stderr).strip() == "the pgai extension is not installed"
    env.pop("VECTORIZER_DB_URL")
    p = subprocess.run(f"python3 -m vectorizer -d '{db_url('postgres', 'cli')}'",
                       shell=True,
                       capture_output=True,
                       text=True,
                       env=env,
                       cwd=vectorizer_src_dir(),
                       )
    assert p.returncode == 1
    assert str(p.stderr).strip() == "the pgai extension is not installed"
