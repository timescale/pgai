import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if enable_vectorizer_tests == "0":
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


def test_embedding_voyageai():
    ok = [
        (
            "select ai.embedding_voyageai('voyage-3-lite', 512)",
            {
                "implementation": "voyageai",
                "config_type": "embedding",
                "model": "voyage-3-lite",
                "dimensions": 512,
                "input_type": "document",
                "api_key_name": "VOYAGE_API_KEY",
            },
        ),
        (
            "select ai.embedding_voyageai('voyage-3-lite', 512, api_key_name => 'TEST_API_KEY', input_type => null)",
            {
                "implementation": "voyageai",
                "config_type": "embedding",
                "model": "voyage-3-lite",
                "dimensions": 512,
                "api_key_name": "TEST_API_KEY",
            },
        ),
        (
            "select ai.embedding_voyageai('voyage-3-lite', 512, api_key_name => 'TEST_API_KEY', input_type => 'query')",
            {
                "implementation": "voyageai",
                "config_type": "embedding",
                "model": "voyage-3-lite",
                "dimensions": 512,
                "input_type": "query",
                "api_key_name": "TEST_API_KEY",
            },
        ),
    ]
    bad = [
        (
            "select ai.embedding_voyageai('voyage-3-lite', 512, input_type => 'foo')",
            'invalid input_type for voyage ai "foo"',
        ),
    ]
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            for query, expected in ok:
                cur.execute(query)
                actual = cur.fetchone()[0]
                assert actual.keys() == expected.keys()
                for k, v in actual.items():
                    assert k in expected and v == expected[k]
            for query, err in bad:
                try:
                    cur.execute(query)
                except psycopg.ProgrammingError as ex:
                    msg = str(ex.args[0])
                    assert len(msg) >= len(err) and msg[: len(err)] == err
                else:
                    pytest.fail(f"expected exception: {err}")


def test_validate_embedding():
    ok = [
        "select ai._validate_embedding( ai.embedding_openai('text-embedding-3-small', 756))",
    ]
    bad = [
        (
            "select ai._validate_embedding(ai.chunking_character_text_splitter(128, 10))",
            "invalid config_type for embedding config",
        ),
        (
            """select ai._validate_embedding('{"config_type": "embedding"}')""",
            "embedding implementation not specified",
        ),
        (
            """select ai._validate_embedding('{"config_type": "embedding", "implementation": "bob"}')""",
            'invalid embedding implementation: "bob"',
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
                    assert len(msg) >= len(err) and msg[: len(err)] == err
                else:
                    pytest.fail(f"expected exception: {err}")
