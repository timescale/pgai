import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def test_loading_row():
    tests = [
        (
            "select ai.loading_row('content')",
            {
                "config_type": "loading",
                "implementation": "row",
                "column_name": "content",
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

def test_loading_document():
    tests = [
        (
            "select ai.loading_document('s3_uri')",
            {
                "config_type": "loading",
                "implementation": "document",
                "column_name": "s3_uri",
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
        """
        select ai._validate_loading
        ( ai.loading_row('body'), 'public', 'thing' )
        """,
        """
        select ai._validate_loading
        ( ai.loading_document('body'), 'public', 'thing' )
        """,
    ]
    bad = [
        (
            """
            select ai._validate_loading
            ( ai.loading_row(), 'public', 'thing' )
            """,
            "function ai.loading_row() does not exist",
        ),
        (
            """
            select ai._validate_loading
            ( ai.loading_document(), 'public', 'thing' )
            """,
            "function ai.loading_document() does not exist",
        ),
        (
            """
            select ai._validate_loading
            ( ai.scheduling_none(), 'public', 'thing' )
            """,
            "invalid config_type for loading config",
        ),
    ]
    with psycopg.connect(db_url("test"), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("drop table if exists public.thing;")
            cur.execute(
                "create table public.thing (id int, color text, weight float, body text)"
            )
            for query in ok:
                cur.execute(query)
                assert True
            for query, err in bad:
                try:
                    cur.execute(query)
                except psycopg.ProgrammingError as ex:
                    msg = str(ex.args[0])
                    assert len(msg) >= len(err) and msg[: len(err)] == err
                else:
                    pytest.fail(f"expected exception: {err}")
