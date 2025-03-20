import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def test_chunking_character_text_splitter():
    tests = [
        (
            "select ai.chunking_none()",
            {
                "implementation": "none",
                "config_type": "chunking",
            },
        ),
        (
            "select ai.chunking_character_text_splitter(128, 10)",
            {
                "separator": "\n\n",
                "is_separator_regex": False,
                "chunk_size": 128,
                "chunk_overlap": 10,
                "implementation": "character_text_splitter",
                "config_type": "chunking",
            },
        ),
        (
            "select ai.chunking_character_text_splitter(256, 20, separator=>E'\n;')",
            {
                "separator": "\n;",
                "is_separator_regex": False,
                "chunk_size": 256,
                "chunk_overlap": 20,
                "implementation": "character_text_splitter",
                "config_type": "chunking",
            },
        ),
        (
            r"""
                select ai.chunking_character_text_splitter
                ( 256
                , 20
                , separator=>'(\s+)'
                , is_separator_regex=>true
                )
            """,
            {
                "separator": r"(\s+)",
                "is_separator_regex": True,
                "chunk_size": 256,
                "chunk_overlap": 20,
                "implementation": "character_text_splitter",
                "config_type": "chunking",
            },
        ),
        (
            # default values of the chunking_character_text_splitter
            "select ai.chunking_character_text_splitter()",
            {
                "separator": "\n\n",
                "is_separator_regex": False,
                "chunk_size": 800,
                "chunk_overlap": 400,
                "implementation": "character_text_splitter",
                "config_type": "chunking",
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


def test_chunking_recursive_character_text_splitter():
    tests = [
        (
            "select ai.chunking_recursive_character_text_splitter(128, 10)",
            {
                "separators": ["\n\n", "\n", ".", "?", "!", " ", ""],
                "is_separator_regex": False,
                "chunk_size": 128,
                "chunk_overlap": 10,
                "implementation": "recursive_character_text_splitter",
                "config_type": "chunking",
            },
        ),
        (
            "select ai.chunking_recursive_character_text_splitter(256, 20, separators=>array[E'\n;', ' '])",
            {
                "separators": ["\n;", " "],
                "is_separator_regex": False,
                "chunk_size": 256,
                "chunk_overlap": 20,
                "implementation": "recursive_character_text_splitter",
                "config_type": "chunking",
            },
        ),
        (
            r"""
                select ai.chunking_recursive_character_text_splitter
                ( 256
                , 20
                , separators=>array['(\s+)']
                , is_separator_regex=>true
                )
            """,
            {
                "separators": [r"(\s+)"],
                "is_separator_regex": True,
                "chunk_size": 256,
                "chunk_overlap": 20,
                "implementation": "recursive_character_text_splitter",
                "config_type": "chunking",
            },
        ),
        (
            # default values of the chunking_recursive_character_text_splitter
            "select ai.chunking_recursive_character_text_splitter()",
            {
                "separators": ["\n\n", "\n", ".", "?", "!", " ", ""],
                "is_separator_regex": False,
                "chunk_size": 800,
                "chunk_overlap": 400,
                "implementation": "recursive_character_text_splitter",
                "config_type": "chunking",
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


def test_validate_chunking():
    ok = [
        """
        select ai._validate_chunking
        ( ai.chunking_character_text_splitter( 128, 10) )
        """,
        """
        select ai._validate_chunking
        ( ai.chunking_recursive_character_text_splitter(128, 10) )
        """,
        """
        select ai._validate_chunking
        ( ai.chunking_none() )
        """,
    ]
    bad = [
        (
            """
            select ai._validate_chunking
            ( ai.scheduling_none() )
            """,
            "invalid config_type for chunking config",
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
