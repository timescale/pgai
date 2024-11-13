import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_secrets_tests = os.getenv("ENABLE_SECRETS_TESTS")
if enable_secrets_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def test_reveal_secrets():
    tests = [
        (
            "",
            """
            select ai.reveal_secret('OPENAI_API_KEY')
            """,
            None,
            False,
        ),
        (
            "SET ai.external_functions_executor_url='http://localhost:8000'",
            """
            select ai.reveal_secret('OPENAI_API_KEY')
            """,
            "test",
            False,
        ),
        (
            "SET ai.openai_api_key='test_guc'",
            """
            select ai.reveal_secret('OPENAI_API_KEY')
            """,
            "test_guc",
            False,
        ),
        (
            # guc overrides secret
            "SET ai.openai_api_key='test_guc'; SET ai.external_functions_executor_url='http://localhost:8000'",
            """
            select ai.reveal_secret('OPENAI_API_KEY')
            """,
            "test_guc",
            False,
        ),
        (
            # guc with different name doesn't override
            "SET ai.openai_api_key='test_guc'; SET ai.external_functions_executor_url='http://localhost:8000'",
            """
            select ai.reveal_secret('OPENAI_API_KEY_2')
            """,
            "test",
            False,
        ),
        (
            # env var overrides secret
            "",
            """
            select ai.reveal_secret('TEST_ENV_SECRET')
            """,
            "super_secret",
            False,
        ),
        (
            # guc overrides env var
            "SET ai.test_env_secret='test_guc'",
            """
            select ai.reveal_secret('TEST_ENV_SECRET')
            """,
            "test_guc",
            False,
        ),
        (
            "SET ai.external_functions_executor_url='http://localhost:8000'",
            """
            select ai.reveal_secret('DOES_NOT_EXIST')
            """,
            None,
            False,
        ),
        (
            "SET ai.external_functions_executor_url='http://localhost:8000'",
            """
            select ai.reveal_secret('ERROR_SECRET')
            """,
            None,
            True,
        ),
    ]
    for setup, query, expected, is_error in tests:
        with psycopg.connect(db_url("test")) as con:
            with con.cursor() as cur:
                cur.execute(setup)
                if is_error:
                    with pytest.raises(Exception):
                        cur.execute(query)
                else:
                    cur.execute(query)
                    actual = cur.fetchone()[0]
                    assert actual == expected


def test_reveal_secret_cache():
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            # enable cache, and populate it
            cur.execute(
                "SET ai.external_functions_executor_url='http://localhost:8000'"
            )
            cur.execute("select ai.reveal_secret('OPENAI_API_KEY')")
            actual = cur.fetchone()[0]
            assert actual == "test"

            cur.execute("select ai.reveal_secret('OPENAI_API_KEY_2')")
            actual = cur.fetchone()[0]
            assert actual == "test"

            # disable fetching the secret from the executor, so returned value can only come from cache
            cur.execute("SET ai.external_functions_executor_url=''")
            # cache works
            cur.execute("select ai.reveal_secret('OPENAI_API_KEY')")
            actual = cur.fetchone()[0]
            assert actual == "test"

            cur.execute("select ai.reveal_secret('OPENAI_API_KEY_2')")
            actual = cur.fetchone()[0]
            assert actual == "test"

            # disable cache, this call will return None since we broke the executor url
            cur.execute("select ai.reveal_secret('OPENAI_API_KEY', false)")
            actual = cur.fetchone()[0]
            assert actual is None

            # make sure disabling the cache also removes the secret from the cache
            cur.execute("select ai.reveal_secret('OPENAI_API_KEY', true)")
            actual = cur.fetchone()[0]
            assert actual is None

            # but the other secret is still in the cache
            cur.execute("select ai.reveal_secret('OPENAI_API_KEY_2', true)")
            actual = cur.fetchone()[0]
            assert actual == "test"
