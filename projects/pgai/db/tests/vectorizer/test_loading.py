import os

import psycopg
import pytest
from psycopg.sql import SQL

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def test_loading_column():
    tests = [
        (
            "select ai.loading_column('content')",
            {
                "config_type": "loading",
                "implementation": "column",
                "column_name": "content",
                "retries": 6,
            },
        ),
        (
            "select ai.loading_column('content', 10)",
            {
                "config_type": "loading",
                "implementation": "column",
                "column_name": "content",
                "retries": 10,
            },
        ),
    ]

    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            for query, expected in tests:
                cur.execute(query)
                actual = cur.fetchone()[0]
                assert actual.keys() == expected.keys()
                for k, v in actual.items():
                    assert k in expected and v == expected[k]


def test_loading_uri():
    tests = [
        (
            "select ai.loading_uri('s3_uri')",
            {
                "config_type": "loading",
                "implementation": "uri",
                "column_name": "s3_uri",
                "retries": 6,
            },
        ),
        (
            "select ai.loading_uri('s3_uri', 3)",
            {
                "config_type": "loading",
                "implementation": "uri",
                "column_name": "s3_uri",
                "retries": 3,
            },
        ),
        (
            "select ai.loading_uri('s3_uri', aws_role_arn => 'arn:aws:iam::account:role/role-name-with-path')",
            {
                "config_type": "loading",
                "implementation": "uri",
                "column_name": "s3_uri",
                "retries": 6,
                "aws_role_arn": "arn:aws:iam::account:role/role-name-with-path",
            },
        ),
    ]

    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            for query, expected in tests:
                cur.execute(query)
                actual = cur.fetchone()[0]
                assert actual.keys() == expected.keys()
                for k, v in actual.items():
                    assert k in expected and v == expected[k]


def test_validate_loading():
    ok = [
        # loading raw text data from a text column
        SQL("""
        select ai._validate_loading
        ( ai.loading_column('body'), 'public', 'thing' )
        """),
        # loading a document from a bytea column
        SQL("""
        select ai._validate_loading
        ( ai.loading_column('document'), 'public', 'thing' )
        """),
        # loading a document from a uri stored in any text column
        # (we do not validate the uri, smart-open does on runtime)
        SQL("""
        select ai._validate_loading
        ( ai.loading_uri('body'), 'public', 'thing' )
        """),
        # setting the aws_role_arn parameter
        SQL("""
        select ai._validate_loading
        ( ai.loading_uri('body', aws_role_arn => 'arn:aws:iam::account:role/role-name-with-path'), 'public', 'thing' )
        """),
    ]
    bad = [
        (
            SQL("""
            select ai._validate_loading
            ( ai.loading_column(), 'public', 'thing' )
            """),
            "function ai.loading_column() does not exist",
        ),
        (
            SQL("""
            select ai._validate_loading
            ( ai.loading_uri(), 'public', 'thing' )
            """),
            "function ai.loading_uri() does not exist",
        ),
        (
            SQL("""
            select ai._validate_loading
            ( ai.loading_column('column_does_not_exist'), 'public', 'thing' )
            """),
            "column_name in config does not exist in the table: column_does_not_exist",
        ),
        (
            SQL("""
            select ai._validate_loading
            ( ai.loading_column('weight'), 'public', 'thing' )
            """),
            "column_name weight in config is of invalid type float8. Supported types are: text, varchar, char, bpchar, bytea",
        ),
        (
            SQL("""
            select ai._validate_loading
            ( ai.loading_uri('weight'), 'public', 'thing' )
            """),
            "column_name weight in config is of invalid type float8. Supported types are: text, varchar, char, bpchar, bytea",
        ),
        (
            SQL("""
            select ai._validate_loading
            ( ai.loading_column('non_existing_column'), 'public', 'thing' )
            """),
            "column_name in config does not exist in the table: non_existing_column",
        ),
        (
            SQL("""
            select ai._validate_loading
            ( ai.loading_uri('non_existing_column'), 'public', 'thing' )
            """),
            "column_name in config does not exist in the table: non_existing_column",
        ),
        (
            SQL("""
            select ai._validate_loading
            ( ai.loading_uri('document'), 'public', 'thing' )
            """),
            "the type of the column `document` in config is not compatible with `uri` loading implementation (type should be either text, varchar, char, bpchar, or bytea)",
        ),
        (
            SQL("""
            select ai._validate_loading
            ( ai.scheduling_none(), 'public', 'thing' )
            """),
            "invalid config_type for loading config",
        ),
        (
            SQL("""
            select ai._validate_loading
            ( ai.loading_column('body', -1), 'public', 'thing' )
            """),
            "invalid loading config, retries must be a non-negative integer",
        ),
        (
            SQL("""
            select ai._validate_loading
            ( ai.loading_uri('body', aws_role_arn => 'foo_bar'), 'public', 'thing' )
            """),
            "invalid loading config, aws_role_arn must match arn:aws:iam::*:role/*",
        ),
    ]
    with psycopg.connect(db_url("test"), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("drop table if exists public.thing;")
            cur.execute(
                "create table public.thing (id int, color text, weight float, body text,document bytea)"
            )
            for query in ok:
                cur.execute(query)
                assert True
            for query, err in bad:
                with pytest.raises(psycopg.ProgrammingError) as ex:
                    cur.execute(query)
                assert str(ex.value).startswith(err)
