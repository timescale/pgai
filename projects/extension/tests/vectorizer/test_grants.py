import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


def test_grant_to():
    tests = [
        (
            "",
            """
            select ai.grant_to()
            """,
            [],
        ),
        (
            "SET ai.grant_to_default='bob, barry, sal'",  # test spaces
            """
            select ai.grant_to()
            """,
            ["bob", "barry", "sal"],
        ),
        (
            "",
            """
            select ai.grant_to('ted')
            """,
            ["ted"],
        ),
        (
            "SET ai.grant_to_default='bob,barry,sal'",
            """
            select ai.grant_to('may')
            """,
            ["barry", "may", "sal", "bob"],
        ),
        (
            "SET ai.grant_to_default='bob , barry , sal '",
            """
            select ai.grant_to(variadic array[]::name[])
            """,
            ["barry", "sal", "bob"],
        ),
        (
            "",
            """
            select ai.grant_to(variadic array[]::name[])
            """,
            [],
        ),
    ]
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            for setup, query, expected in tests:
                cur.execute(setup)
                cur.execute(query)
                actual = cur.fetchone()[0]
                assert actual.sort() == expected.sort()
