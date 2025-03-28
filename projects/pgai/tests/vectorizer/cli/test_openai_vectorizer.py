import logging
import os
from typing import Any

import openai
import pytest
from psycopg import Connection
from psycopg.rows import dict_row

from tests.vectorizer import expected
from tests.vectorizer.cli.conftest import (
    TestDatabase,
    configure_vectorizer,
    run_vectorizer_worker,
    setup_source_table,
)


def configure_openai_vectorizer(
    connection: Connection,
    openai_proxy_url: str | None = None,
    number_of_rows: int = 1,
    concurrency: int = 1,
    batch_size: int = 1,
    chunking: str = "chunking_character_text_splitter()",
    formatting: str = "formatting_python_template('$chunk')",
) -> int:
    """Creates and configures a vectorizer for testing"""
    table_name = setup_source_table(connection, number_of_rows)
    base_url = (
        f", base_url => '{openai_proxy_url}'" if openai_proxy_url is not None else ""
    )

    embedding = f"embedding_openai('text-embedding-ada-002', 1536{base_url})"
    return configure_vectorizer(
        table_name,
        connection,
        concurrency=concurrency,
        batch_size=batch_size,
        chunking=chunking,
        formatting=formatting,
        embedding=embedding,
    )


@pytest.mark.parametrize(
    "num_items,concurrency,batch_size,openai_proxy_url,secrets_from_db",
    [
        (1, 1, 1, None, False),
        (1, 1, 1, 8000, False),
        (4, 2, 2, None, False),
        (1, 1, 1, None, True),
        (4, 2, 2, None, True),
    ],
    indirect=["openai_proxy_url"],
)
def test_process_vectorizer(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
    num_items: int,
    concurrency: int,
    batch_size: int,
    openai_proxy_url: str | None,
    secrets_from_db: bool,
):
    """Test successful processing of vectorizer tasks"""
    _, conn = cli_db
    vectorizer_id = configure_openai_vectorizer(
        cli_db[1],
        openai_proxy_url,
        number_of_rows=num_items,
        concurrency=concurrency,
        batch_size=batch_size,
    )
    # Insert pre-existing embedding for first item
    with conn.cursor() as cur:
        cur.execute("""
           INSERT INTO
           blog_embedding_store(embedding_uuid, id, chunk_seq, chunk, embedding)
           VALUES (gen_random_uuid(), 1, 1, 'post_1',
            array_fill(0, ARRAY[1536])::vector)
        """)

    if secrets_from_db:
        # create extension to test loading secret from db
        conn.execute("""CREATE EXTENSION IF NOT EXISTS ai CASCADE""")
        # Ensuring no OPENAI_API_KEY env set for the worker
        # to test loading secret from db
        del os.environ["OPENAI_API_KEY"]

    # When running the worker with cassette matching original test params
    cassette = (
        f"openai-character_text_splitter-chunk_value-"
        f"items={num_items}-batch_size={batch_size}-"
        f"custom_base_url={openai_proxy_url is not None}.yaml"
    )
    # logging.getLogger("vcr").setLevel(logging.DEBUG)

    with vcr_.use_cassette(cassette):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id, concurrency)

    print(f"result: {result.stdout}")
    assert not result.exception
    assert result.exit_code == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as count FROM blog_embedding_store;")
        assert cur.fetchone()["count"] == num_items  # type: ignore

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM ai.vectorizer_worker_process;")
        row = cur.fetchone()
        assert row is not None
        assert row["started"] is not None
        assert row["last_heartbeat"] is not None
        assert row["heartbeat_count"] >= 1
        assert row["error_count"] == 0
        assert row["last_error_at"] is None
        assert row["last_error_message"] is None
        assert row["success_count"] == num_items
        worker_id = row["id"]
        assert cur.fetchone() is None

        cur.execute("SELECT * FROM ai.vectorizer_worker_progress;")
        row = cur.fetchone()
        assert row is not None
        assert row["last_success_at"] is not None
        assert row["last_success_process_id"] == worker_id
        assert row["last_error_at"] is None
        assert row["last_error_message"] is None
        assert row["last_error_process_id"] is None
        assert row["success_count"] == num_items
        assert cur.fetchone() is None


@pytest.mark.postgres_params(load_openai_key=False)
def test_vectorizer_without_secrets_fails(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    _, conn = cli_db
    vectorizer_id = configure_openai_vectorizer(cli_db[1])
    # Insert pre-existing embedding for first item
    with conn.cursor() as cur:
        cur.execute("""
           INSERT INTO
           blog_embedding_store(embedding_uuid, id, chunk_seq, chunk, embedding)
           VALUES (gen_random_uuid(), 1, 1, 'post_1',
            array_fill(0, ARRAY[1536])::vector)
                """)
    # Ensuring no OPENAI_API_KEY env set for the worker
    del os.environ["OPENAI_API_KEY"]

    cassette = "openai-character_text_splitter-chunk_value-items=1-batch_size=1.yaml"
    logging.getLogger("vcr").setLevel(logging.DEBUG)
    with vcr_.use_cassette(cassette):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 1
    assert "ApiKeyNotFoundError" in result.output
    print(f"result: {result.stdout}")

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM ai.vectorizer_worker_process;")
        row = cur.fetchone()
        assert row is not None
        assert row["started"] is not None
        assert row["last_heartbeat"] is not None
        assert row["heartbeat_count"] >= 1
        assert row["error_count"] == 1
        assert row["success_count"] == 0
        assert row["last_error_at"] is not None
        assert row["last_error_message"] is not None
        worker_id = row["id"]
        assert cur.fetchone() is None

        cur.execute("SELECT * FROM ai.vectorizer_worker_progress;")
        row = cur.fetchone()
        assert row is not None
        assert row["last_success_at"] is None
        assert row["last_success_process_id"] is None
        assert row["last_error_at"] is not None
        assert row["last_error_message"] is not None
        assert row["last_error_process_id"] == worker_id
        assert row["success_count"] == 0
        assert cur.fetchone() is None


def test_document_exceeds_model_context_length(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test handling of documents that exceed the model's token limit"""
    _, conn = cli_db
    # Given a vectorizer configuration
    vectorizer_id = configure_openai_vectorizer(
        cli_db[1],
        number_of_rows=2,
        batch_size=2,
        chunking="chunking_recursive_character_text_splitter(128, 10,"
        " separators => array[E'\n\n'])",
    )
    with conn.cursor(row_factory=dict_row) as cur:
        long_content = "AGI" * 5000
        cur.execute(
            f"UPDATE blog SET CONTENT = '{long_content}' where id = '2'",
        )

    # When running the worker
    with vcr_.use_cassette("test_document_in_batch_too_long.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 0

    # Then only the normal document should be embedded
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM blog_embedding_store ORDER BY id")
        records = cur.fetchall()
        assert len(records) == 2
        record = records[0]

        # Verify the embedded document
        assert record["id"] == 1
        assert record["chunk"] == "post_1"
        assert (
            record["embedding"]
            == expected.embeddings["openai-character_text_splitter-chunk_value-1-1"][0]
        )

        record = records[1]

        assert record["id"] == 2
        assert record["chunk"] == long_content[:15001]
        assert (
            record["embedding"]
            == expected.embeddings["openai-character_text_splitter-chunk_value-1-1"][1]
        )

        # Check error was logged
        cur.execute("SELECT * FROM ai.vectorizer_errors")
        errors = cur.fetchall()
        assert len(errors) == 0


def test_invalid_api_key_error(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that worker handles invalid API key appropriately"""
    _, conn = cli_db

    vectorizer_id = configure_openai_vectorizer(
        cli_db[1],
        number_of_rows=2,
        batch_size=2,
        chunking="chunking_recursive_character_text_splitter()",
    )

    os.environ["OPENAI_API_KEY"] = "invalid"

    # When running the worker and getting an invalid api key response
    with vcr_.use_cassette("test_invalid_api_key_error.yaml"):
        try:
            run_vectorizer_worker(cli_db_url, vectorizer_id)
        except openai.AuthenticationError as e:
            assert e.code == 401

    # Ensure there's an entry in the errors table
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM ai.vectorizer_errors")
        records = cur.fetchall()
        assert len(records) == 1
        error = records[0]
        assert error["id"] == vectorizer_id
        assert error["message"] == "embedding provider failed"
        assert error["details"] == {
            "provider": "openai",
            "error_reason": "Error code: 401 - {'error': {'message': "
            "'Incorrect API key provided: invalid."
            " You can find your API key at"
            " https://platform.openai.com/account/api-keys.',"
            " 'type': 'invalid_request_error', 'param': None,"
            " 'code': 'invalid_api_key'}}",
        }


def test_invalid_function_arguments(
    cli_db: tuple[TestDatabase, Connection], cli_db_url: str
):
    """Test that worker handles invalid embedding model arguments appropriately"""
    _, conn = cli_db

    vectorizer_id = configure_openai_vectorizer(cli_db[1])
    # And a vectorizer with invalid embedding dimensions
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ai.vectorizer
            SET config = jsonb_set(
                config,
                '{embedding,dimensions}',
                '128'::jsonb
            )
            WHERE id = %s
        """,
            (vectorizer_id,),
        )

    # When running the worker
    try:
        run_vectorizer_worker(cli_db_url, vectorizer_id)
    except ValueError as e:
        assert str(e) == "dimensions must be 1536 for text-embedding-ada-002"

    # Then an error was logged
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM ai.vectorizer_errors")
        records = cur.fetchall()
        assert len(records) == 1
        error = records[0]
        assert error["id"] == vectorizer_id
        assert error["message"] == "embedding provider failed"
        assert error["details"] == {
            "provider": "openai",
            "error_reason": "dimensions must be 1536 for text-embedding-ada-002",
        }
