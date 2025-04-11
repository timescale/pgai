import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_vectorizer_tests = os.getenv("ENABLE_VECTORIZER_TESTS")
if enable_vectorizer_tests == "0":
    pytest.skip(allow_module_level=True)


def db_url(user: str) -> str:
    return f"postgres://{user}@127.0.0.1:5432/test"


@pytest.mark.parametrize(
    "destination_config,expected_config",
    [
        (
            "select ai.destination_table(target_schema => 'my_schema', target_table => 'my_table')",
            {
                "config_type": "destination",
                "implementation": "table",
                "target_schema": "my_schema",
                "target_table": "my_table",
            },
        ),
        (
            "select ai.destination_table("
            "target_schema => 'my_schema'"
            ", target_table => 'my_table'"
            ", view_schema => 'my_schema'"
            ", view_name => 'my_view'"
            ")",
            {
                "config_type": "destination",
                "implementation": "table",
                "target_schema": "my_schema",
                "target_table": "my_table",
                "view_schema": "my_schema",
                "view_name": "my_view",
            },
        ),
    ],
)
def test_destination_table(destination_config, expected_config):
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            cur.execute(destination_config)
            actual = cur.fetchone()[0]
            assert actual.keys() == expected_config.keys()
            for k, v in actual.items():
                assert k in expected_config and v == expected_config[k]


@pytest.mark.parametrize(
    "destination_config,expected_config",
    [
        (
            "select ai.destination_column('embedding')",
            {
                "implementation": "column",
                "embedding_column": "embedding",
                "config_type": "destination",
            },
        ),
        (
            "select ai.destination_column('vector_embedding')",
            {
                "implementation": "column",
                "embedding_column": "vector_embedding",
                "config_type": "destination",
            },
        ),
    ],
)
def test_destination_column(destination_config, expected_config):
    with psycopg.connect(db_url("test")) as con:
        with con.cursor() as cur:
            cur.execute(destination_config)
            actual = cur.fetchone()[0]
            assert actual.keys() == expected_config.keys()
            for k, v in actual.items():
                assert k in expected_config and v == expected_config[k]


@pytest.mark.parametrize(
    "destination,chunking",
    [
        ("ai.destination_table('my_schema', 'my_table')", "ai.chunking_none()"),
        (
            "ai.destination_table('my_schema', 'my_table')",
            "ai.chunking_character_text_splitter()",
        ),
        (
            "ai.destination_table('my_schema', 'my_table')",
            "ai.chunking_recursive_character_text_splitter()",
        ),
        ("ai.destination_column('embedding')", "ai.chunking_none()"),
    ],
)
def test_validate_destination_valid(destination, chunking):
    with psycopg.connect(db_url("test"), autocommit=True) as con:
        with con.cursor() as cur:
            query = f"""
            select ai._validate_destination(
                {destination}, {chunking}
            )
            """
            cur.execute(query)
            assert True


@pytest.mark.parametrize(
    "destination,chunking,expected_error",
    [
        (
            "ai.chunking_none()",
            "ai.chunking_none()",
            "invalid config_type for destination config",
        ),
        (
            "ai.destination_column('embedding')",
            "ai.chunking_character_text_splitter()",
            "chunking must be none for column destination",
        ),
        (
            "ai.destination_column('embedding')",
            "ai.chunking_recursive_character_text_splitter()",
            "chunking must be none for column destination",
        ),
    ],
)
def test_validate_destination_invalid(destination, chunking, expected_error):
    with psycopg.connect(db_url("test"), autocommit=True) as con:
        with con.cursor() as cur:
            query = f"""
            select ai._validate_destination(
                {destination}, {chunking}
            )
            """
            try:
                cur.execute(query)
            except psycopg.ProgrammingError as ex:
                msg = str(ex.args[0])
                assert (
                    len(msg) >= len(expected_error)
                    and msg[: len(expected_error)] == expected_error
                )
            else:
                pytest.fail(f"expected exception: {expected_error}")
