import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if not enable_vectorizer_tests or enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def test_embedding_openai():
    tests = [
        (
            "select ai.embedding_openai('text-embedding-3-small', 128)",
            {
                "implementation": "openai",
                "config_type": "embedding",
                "model": "text-embedding-3-small",
                "dimensions": 128,
                "api_key_name": "OPENAI_API_KEY",
            },
        ),
        (
            """select ai.embedding_openai('text-embedding-3-small', 128, chat_user=>'bob')""",
            {
                "implementation": "openai",
                "config_type": "embedding",
                "model": "text-embedding-3-small",
                "dimensions": 128,
                "user": "bob",
                "api_key_name": "OPENAI_API_KEY",
            },
        ),
        (
            "select ai.embedding_openai('text-embedding-3-small', 128, api_key_name=>'DEV_API_KEY')",
            {
                "implementation": "openai",
                "config_type": "embedding",
                "model": "text-embedding-3-small",
                "dimensions": 128,
                "api_key_name": "DEV_API_KEY",
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

