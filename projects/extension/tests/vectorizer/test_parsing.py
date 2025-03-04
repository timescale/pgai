import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def test_parsing():
    tests = [
        (
            "select ai.parsing_docling()",
            {
                "config_type": "parsing",
                "implementation": "docling",
            },
        ),
        (
            "select ai.parsing_pymupdf()",
            {
                "config_type": "parsing",
                "implementation": "pymupdf",
            },
        ),
        (
            "select ai.parsing_auto()",
            {
                "config_type": "parsing",
                "implementation": "auto",
            },
        ),
        (
            "select ai.parsing_none()",
            {
                "config_type": "parsing",
                "implementation": "none",
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


def test_validate_parsing():
    ok = [
        """
        select ai._validate_parsing(
            ai.parsing_auto(),
            ai.loading_column('body'),
            'public',
            'thing'
        )
        """,
        """
        select ai._validate_parsing(
            ai.parsing_auto(),
            ai.loading_column('column'),
            'public',
            'thing'
        )
        """,
        """
        select ai._validate_parsing(
            ai.parsing_docling(),
            ai.loading_column('column'),
            'public',
            'thing'
        )
        """,
        """
        select ai._validate_parsing(
            ai.parsing_pymupdf(),
            ai.loading_column('column'),
            'public',
            'thing'
        )
        """,
    ]
    bad = [
        (
            """
            select ai._validate_parsing(
                ai.parsing_docling(),
                ai.loading_column('body'),
                'public',
                'thing'
            )
            """,
            "parsing_docling must be used with a bytea column",
        ),
        (
            """
            select ai._validate_parsing(
                ai.parsing_pymupdf(),
                ai.loading_column('body'),
                'public',
                'thing'
            )
            """,
            "parsing_pymupdf must be used with a bytea column",
        ),
        (
            """
            select ai._validate_parsing(
                ai.parsing_none(),
                ai.loading_column('document'),
                'public',
                'thing'
            )
            """,
            "cannot use parsing_none with bytea columns",
        ),
    ]
    with psycopg.connect(db_url("test"), autocommit=True) as con:
        with con.cursor() as cur:
            cur.execute("drop table if exists public.thing;")
            cur.execute(
                "create table public.thing (id int, color text, weight float, body text, document bytea)"
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
