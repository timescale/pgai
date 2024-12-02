import os
import subprocess
from pathlib import Path

import pytest
import psycopg


@pytest.fixture(scope="module", autouse=True)
def set_up_test_db() -> None:
    # create a test user and test database owned by the test user
    with psycopg.connect(
        "postgres://postgres@127.0.0.1:5432/postgres", autocommit=True
    ) as con:
        with con.cursor() as cur:
            cur.execute("drop database if exists text_to_sql with (force)")
            cur.execute("create database text_to_sql owner test")
    # use the test user to create the extension in the text_to_sql database
    with psycopg.connect("postgres://test@127.0.0.1:5432/text_to_sql") as con:
        with con.cursor() as cur:
            # turn on the feature flag for text_to_sql
            cur.execute(
                "select set_config('ai.enable_feature_flag_text_to_sql', 'true', false)"
            )
            cur.execute("create extension ai cascade")


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/text_to_sql"


def where_am_i() -> str:
    if "WHERE_AM_I" in os.environ and os.environ["WHERE_AM_I"] == "docker":
        return "docker"
    return "host"


def docker_dir() -> str:
    return "/pgai/tests/text_to_sql"


def host_dir() -> Path:
    return Path(__file__).parent.absolute()


def snapshot_descriptions(name: str) -> None:
    host_dir().joinpath(f"{name}.actual").unlink(missing_ok=True)
    cmd = " ".join(
        [
            "psql",
            f'''-d "{db_url("test")}"''',
            "-v ON_ERROR_STOP=1",
            "-X",
            f"-o {docker_dir()}/{name}.actual",
            '-c "select objtype, objnames, objargs, description from ai.description order by 1,2,3"',
        ]
    )
    if where_am_i() != "docker":
        cmd = f"docker exec -w {docker_dir()} pgai-ext {cmd}"
    subprocess.run(cmd, check=True, shell=True, env=os.environ, cwd=str(host_dir()))


def file_contents(name: str) -> str:
    return host_dir().joinpath(f"{name}").read_text()


def test_description():
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            cur.execute("""
            create table bob
            ( id int not null primary key
            , foo text not null
            , bar timestamptz not null default now()
            );

            create view bobby as
            select * from bob;

            create function life(x int) returns int
            as $func$select 42$func$ language sql;
            """)

            cur.execute("""
            -- table
            select ai.set_table_description('bob', 'this is a comment about the bob table');
            select ai.set_column_description('bob', 'id', 'this is a comment about the id column');
            select ai.set_column_description('bob', 'foo', 'this is a comment about the foo column');
            select ai.set_column_description('bob', 'bar', 'this is a comment about the bar column');

            -- view
            select ai.set_view_description('bobby', 'this is a comment about the bob table');
            select ai.set_column_description('bobby', 'id', 'this is a comment about the id column');
            select ai.set_column_description('bobby', 'foo', 'this is a comment about the foo column');
            select ai.set_column_description('bobby', 'bar', 'this is a comment about the bar column');

            -- function
            select ai.set_function_description('life'::regproc, 'this is a comment about the life function');
            """)
            con.commit()
            snapshot_descriptions("0")
            actual = file_contents("0.actual")
            expected = file_contents("0.expected")
            assert actual == expected

            # change descriptions
            cur.execute(
                "select ai.set_table_description('bob', 'this is a BETTER comment about the bob table')"
            )
            cur.execute(
                "select ai.set_column_description('bobby', 'id', 'this is a BETTER comment about the id column')"
            )
            cur.execute(
                """
                select ai.set_function_description
                ( 'life'::regproc
                , 'this is a BETTER comment about the life function'
                )
                """
            )
            con.commit()
            snapshot_descriptions("1")
            actual = file_contents("1.actual")
            expected = file_contents("1.expected")
            assert actual == expected

            # rename function
            cur.execute("alter function life(int) rename to death")
            con.commit()
            snapshot_descriptions("2")
            actual = file_contents("2.actual")
            expected = file_contents("2.expected")
            assert actual == expected

            # rename table column
            cur.execute("alter table bob rename column foo to baz")
            con.commit()
            snapshot_descriptions("3")
            actual = file_contents("3.actual")
            expected = file_contents("3.expected")
            assert actual == expected

            # rename view
            cur.execute("alter view bobby rename to frederick")
            con.commit()
            snapshot_descriptions("4")
            actual = file_contents("4.actual")
            expected = file_contents("4.expected")
            assert actual == expected

            # drop view
            cur.execute("drop view frederick")
            con.commit()
            snapshot_descriptions("5")
            actual = file_contents("5.actual")
            expected = file_contents("5.expected")
            assert actual == expected

            # drop table column
            cur.execute("alter table bob drop column baz")
            con.commit()
            snapshot_descriptions("6")
            actual = file_contents("6.actual")
            expected = file_contents("6.expected")
            assert actual == expected

            # alter function set schema
            cur.execute("create schema maria")
            cur.execute("alter function death set schema maria")
            con.commit()
            snapshot_descriptions("7")
            actual = file_contents("7.actual")
            expected = file_contents("7.expected")
            assert actual == expected

            # alter table set schema
            cur.execute("alter table bob set schema maria")
            con.commit()
            snapshot_descriptions("8")
            actual = file_contents("8.actual")
            expected = file_contents("8.expected")
            assert actual == expected

            # test overloaded function names
            cur.execute("""
            create function maria.death(x int, y int) returns int
            as $func$select 42$func$ language sql;
            """)
            cur.execute(
                "select ai.set_function_description('maria.death(int, int)', 'overloaded')"
            )
            con.commit()
            snapshot_descriptions("9")
            actual = file_contents("9.actual")
            expected = file_contents("9.expected")
            assert actual == expected

            # drop function
            cur.execute("drop function maria.death(int)")
            con.commit()
            snapshot_descriptions("10")
            actual = file_contents("10.actual")
            expected = file_contents("10.expected")
            assert actual == expected

            # drop table
            cur.execute("drop table maria.bob")
            con.commit()
            snapshot_descriptions("11")
            actual = file_contents("11.actual")
            expected = file_contents("11.expected")
            assert actual == expected

            # drop schema cascade
            cur.execute("drop schema maria cascade")
            con.commit()
            snapshot_descriptions("12")
            actual = file_contents("12.actual")
            expected = file_contents("12.expected")
            assert actual == expected
