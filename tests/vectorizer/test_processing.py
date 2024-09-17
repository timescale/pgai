import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if not enable_vectorizer_tests or enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def test_processing_none():
    tests = [
        (
            "select ai.processing_none()",
            {
                "implementation": "none",
                "config_type": "processing",
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


def test_processing_cloud_functions():
    tests = [
        (
            "select ai.processing_cloud_functions()",
            {
                "implementation": "cloud_functions",
                "config_type": "processing",
                "batch_size": 50,
            },
        ),
        (
            "select ai.processing_cloud_functions(batch_size=>500)",
            {
                "implementation": "cloud_functions",
                "config_type": "processing",
                "batch_size": 500,
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


def test_validate_processing():
    ok = [
        "select ai._validate_processing(ai.processing_none())",
        "select ai._validate_processing(ai.processing_cloud_functions())",
        "select ai._validate_processing(ai.processing_cloud_functions(batch_size=>500))",
        "select ai._validate_processing(ai.processing_cloud_functions(batch_size=>2048))",
    ]
    bad = [
        (
            "select ai._validate_processing(ai.indexing_hnsw())",
            "invalid config_type for processing config"
        ),
        (
            """select ai._validate_processing('{"config_type": "processing"}'::jsonb)""",
            "processing implementation not specified"
        ),
        (
            """
            select ai._validate_processing
            ( '{"config_type": "processing", "implementation": "grandfather clock"}'::jsonb
            )
            """,
            'unrecognized processing implementation: "grandfather clock"'
        ),
        (
            """
            select ai._validate_processing
            ( ai.processing_cloud_functions(batch_size=>2049)
            )
            """,
            'batch_size must be less than or equal to 2048'
        ),
    ]
    with psycopg.connect(db_url("test"), autocommit=True) as con:
        with con.cursor() as cur:
            for query in ok:
                cur.execute(query)
                assert True
            for query, err in bad:
                try:
                    cur.execute(query)
                except psycopg.ProgrammingError as ex:
                    msg = str(ex.args[0])
                    assert len(msg) >= len(err) and msg[:len(err)] == err
                else:
                    pytest.fail(f"expected exception: {err}")

