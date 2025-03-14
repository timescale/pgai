import json
import logging
import os
import re
from typing import Any

import openai
import pytest
import vcr  # type:ignore
from psycopg import Connection
from psycopg.rows import dict_row

from tests.vectorizer.cli.conftest import (
    TestDatabase,
    configure_vectorizer,
    run_vectorizer_worker,
    setup_source_table,
)


def configure_openai_vectorizer(
    connection: Connection,
    number_of_rows: int = 1,
    concurrency: int = 1,
    batch_size: int = 1,
    chunking: str = "chunking_character_text_splitter('content')",
    formatting: str = "formatting_python_template('$chunk')",
) -> int:
    """Creates and configures a vectorizer for testing"""
    table_name = setup_source_table(connection, number_of_rows)

    embedding = (
        f"embedding_openai('text-embedding-ada-002', 1536, async_batch_enabled=>true)"  # noqa
    )
    return configure_vectorizer(
        table_name,
        connection,
        concurrency=concurrency,
        batch_size=batch_size,
        chunking=chunking,
        formatting=formatting,
        embedding=embedding,
    )


def rewrite_request_boundary(request):  # type:ignore
    content_type = request.headers.get("Content-Type", "")  # type:ignore
    if "multipart/form-data" in content_type:
        fixed_boundary = "fixedboundary"
        request.headers["Content-Type"] = re.sub(  # type:ignore
            r"boundary=[^\s;]+",
            f"boundary={fixed_boundary}",
            content_type,  # type:ignore
        )
        if request.body:  # type:ignore
            request.body = re.sub(
                rb"--[^\s\r\n]+",
                b"--" + fixed_boundary.encode(),
                request.body,  # type:ignore
            )
    return request  # type:ignore


@pytest.mark.parametrize(
    "num_items,concurrency,batch_size",
    [
        (1, 1, 1),
        # (4, 2, 2),
    ],
)
def test_create_async_batch(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
    num_items: int,
    concurrency: int,
    batch_size: int,
):
    """Test successful processing of vectorizer tasks"""
    _, conn = cli_db
    vectorizer_id = configure_openai_vectorizer(
        cli_db[1],
        number_of_rows=num_items,
        concurrency=concurrency,
        batch_size=batch_size,
    )
    # TODO: should we delete the old one first?
    # Insert pre-existing embedding for first item
    with conn.cursor() as cur:
        cur.execute("""
           INSERT INTO
           blog_embedding_store(embedding_uuid, id, chunk_seq, chunk, embedding)
           VALUES (gen_random_uuid(), 1, 1, 'post_1',
            array_fill(0, ARRAY[1536])::vector)
        """)

    # Ensuring no OPENAI_API_KEY env set for the worker
    # to test loading secret from db
    del os.environ["OPENAI_API_KEY"]

    # When running the worker with cassette matching original test params
    cassette = (
        f"openai-character_text_splitter-chunk_value-"
        f"items={num_items}-batch_size={batch_size}-"
        "async_batch=True.yaml"
    )
    logging.getLogger("vcr").setLevel(logging.DEBUG)

    vcr_with_boundary_overwrite = vcr.VCR(
        serializer=vcr_.serializer,
        cassette_library_dir=vcr_.cassette_library_dir,
        record_mode=vcr_.record_mode,
        filter_headers=vcr_.filter_headers,
        match_on=vcr_.match_on,
        before_record_response=vcr_.before_record_response,
        before_record_request=rewrite_request_boundary,
    )

    # We need to add cassette requests that return the status of the batches
    # are pending.
    with vcr_with_boundary_overwrite.use_cassette(cassette):  # type:ignore
        result = run_vectorizer_worker(cli_db_url, vectorizer_id, concurrency)

    assert not result.exception, result.stdout
    assert result.exit_code == 0

    # When updating the test and re-creating the cassettes, update the batch id
    # and file id from the content of the cassette's reponse
    #
    # This is the case of a single batch is created.
    single_batch_id = "batch_67cf68323760819097ce6ea8b3337bfa"
    single_file_id = "file-3fDziK93Ez1753RgHZYyxK"
    # These are for the case with 2 batches.
    batch_id_1 = "batch_67d03843e98881909b094583dc24dc52"
    file_id_1 = "file-KBnxVWzzTtUgzaLR8mavi5"
    batch_id_2 = "batch_67d0384485f48190bfba6d5fc4f6854f"
    file_id_2 = "file-P2S2bhVE9Keyn66MoZ6ktx"

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as count FROM blog_embedding_store;")
        assert cur.fetchone()["count"] == 0  # type: ignore

        # Check batches in the queue
        cur.execute("""
            SELECT id, status, metadata->>'input_file_id' as input_file_id
            FROM ai._vectorizer_async_batch_q_1
            ORDER BY id;
        """)
        batches = cur.fetchall()

        if num_items == 1:
            assert len(batches) == 1
            assert batches[0] == {
                "id": single_batch_id,
                "status": "pending",
                "input_file_id": single_file_id,
            }
        elif num_items == 4:
            assert len(batches) == 2
            # First batch
            assert batches[0] == {
                "id": batch_id_1,
                "status": "pending",
                "input_file_id": file_id_1,
            }
            # Second batch
            assert batches[1] == {
                "id": batch_id_2,
                "status": "validating",
                "input_file_id": file_id_2,
            }

        # Check chunks for each batch
        cur.execute("""
            SELECT id, chunk_seq, async_batch_id, chunk
            FROM ai._vectorizer_async_batch_chunks_1
            ORDER BY async_batch_id, id, chunk_seq;
        """)
        chunks = cur.fetchall()

        if num_items == 1:
            assert len(chunks) == 1
            assert chunks[0] == {
                "id": 1,
                "chunk_seq": 0,
                "async_batch_id": single_batch_id,
                "chunk": "post_1",
            }
        elif num_items == 4:
            assert len(chunks) == 4
            # First batch chunks
            assert chunks[0] == {
                "id": 1,
                "chunk_seq": 0,
                "async_batch_id": batch_id_1,
                "chunk": "post_1",
            }
            assert chunks[1] == {
                "id": 2,
                "chunk_seq": 0,
                "async_batch_id": batch_id_1,
                "chunk": "post_2",
            }
            # Second batch chunks
            assert chunks[2] == {
                "id": 3,
                "chunk_seq": 0,
                "async_batch_id": batch_id_2,
                "chunk": "post_3",
            }
            assert chunks[3] == {
                "id": 4,
                "chunk_seq": 0,
                "async_batch_id": batch_id_2,
                "chunk": "post_4",
            }


@pytest.mark.parametrize(
    "num_items,concurrency,batch_size",
    [
        (1, 1, 1),
        # (4, 2, 2),
    ],
)
def test_process_async_batch(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
    num_items: int,
    concurrency: int,
    batch_size: int,
):
    """Test successful processing of vectorizer tasks"""
    _, conn = cli_db
    vectorizer_id = configure_openai_vectorizer(
        cli_db[1],
        number_of_rows=0,  # The items are pending in the async batch.
        concurrency=concurrency,
        batch_size=batch_size,
    )

    single_batch_id = "batch_67cf68323760819097ce6ea8b3337bfa"
    single_file_id = "file-3fDziK93Ez1753RgHZYyxK"
    batch_id_1 = "batch_67d03843e98881909b094583dc24dc52"
    file_id_1 = "file-KBnxVWzzTtUgzaLR8mavi5"
    batch_id_2 = "batch_67d0384485f48190bfba6d5fc4f6854f"
    file_id_2 = "file-P2S2bhVE9Keyn66MoZ6ktx"

    with conn.cursor() as cur:
        # Insert batches
        if num_items == 1:
            cur.execute(
                """
                INSERT INTO ai._vectorizer_async_batch_q_1
                (id, status, errors, metadata, next_attempt_after)
                VALUES (%s, %s, %s, %s, now())
            """,
                (
                    single_batch_id,
                    "pending",
                    None,
                    json.dumps({"input_file_id": single_file_id}),
                ),
            )

            # Insert single chunk
            cur.execute(
                """
                INSERT INTO ai._vectorizer_async_batch_chunks_1
                (id, chunk_seq, async_batch_id, chunk)
                VALUES (%s, %s, %s, %s)
            """,
                (1, 0, single_batch_id, "post_1"),
            )

        elif num_items == 4:
            # Insert first batch
            cur.execute(
                """
                INSERT INTO ai._vectorizer_async_batch_q_1
                (id, status, errors, metadata, next_attempt_after)
                VALUES (%s, %s, %s, %s, now())
            """,
                (
                    batch_id_1,
                    "pending",
                    None,
                    json.dumps({"input_file_id": file_id_1}),
                    None,
                    0,
                ),
            )

            # Insert second batch
            cur.execute(
                """
                INSERT INTO ai._vectorizer_async_batch_q_1
                (id, status, errors, metadata, next_attempt_after)
                VALUES (%s, %s, %s, %s, now())
            """,
                (
                    batch_id_2,
                    "validating",
                    None,
                    json.dumps({"input_file_id": file_id_2}),
                    None,
                    0,
                ),
            )

            # Insert chunks for first batch
            cur.execute(
                """
                INSERT INTO ai._vectorizer_async_batch_chunks_1
                (id, chunk_seq, async_batch_id, chunk)
                VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)
            """,
                (1, 0, batch_id_1, "post_1", 2, 0, batch_id_1, "post_2"),
            )

            # Insert chunks for second batch
            cur.execute(
                """
                INSERT INTO ai._vectorizer_async_batch_chunks_1
                (id, chunk_seq, async_batch_id, chunk)
                VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)
            """,
                (3, 0, batch_id_2, "post_3", 4, 0, batch_id_2, "post_4"),
            )

    # TODO: if we decide to delete existing embeddings here we should
    # insert some data into the store here.

    # Ensuring no OPENAI_API_KEY env set for the worker
    # to test loading secret from db
    del os.environ["OPENAI_API_KEY"]

    # When running the worker with cassette matching original test params
    cassette = (
        f"openai-character_text_splitter-chunk_value-"
        f"items={num_items}-batch_size={batch_size}-"
        "async_batch=True.yaml"
    )
    logging.getLogger("vcr").setLevel(logging.DEBUG)

    vcr_with_boundary_overwrite = vcr.VCR(
        serializer=vcr_.serializer,
        cassette_library_dir=vcr_.cassette_library_dir,
        record_mode=vcr.mode.NEW_EPISODES,
        filter_headers=vcr_.filter_headers,
        match_on=vcr_.match_on,
        before_record_response=vcr_.before_record_response,
        before_record_request=rewrite_request_boundary,
    )

    with vcr_with_boundary_overwrite.use_cassette(cassette):  # type:ignore
        result = run_vectorizer_worker(cli_db_url, vectorizer_id, concurrency)

    assert not result.exception, result.stdout
    assert result.exit_code == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as count FROM blog_embedding_store;")
        assert cur.fetchone()["count"] == num_items  # type: ignore
        cur.execute("SELECT count(*) as count FROM ai._vectorizer_q_1;")
        assert cur.fetchone()["count"] == 0  # type: ignore
        cur.execute("SELECT count(*) as count FROM ai._vectorizer_async_batch_q_1;")
        assert cur.fetchone()["count"] == 0  # type: ignore
        cur.execute(
            "SELECT count(*) as count FROM ai._vectorizer_async_batch_chunks_1;"
        )
        assert cur.fetchone()["count"] == 0  # type: ignore


@pytest.mark.parametrize(
    "num_items,concurrency,batch_size",
    [
        (1, 1, 1),
    ],
)
def test_process_async_batch_fail_step_import(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
    num_items: int,
    concurrency: int,
    batch_size: int,
):
    """Test successful processing of vectorizer tasks"""
    _, conn = cli_db
    vectorizer_id = configure_openai_vectorizer(
        cli_db[1],
        number_of_rows=0,  # The items are pending in the async batch.
        concurrency=concurrency,
        batch_size=batch_size,
    )

    single_batch_id = "batch_67cf68323760819097ce6ea8b3337bfb"
    single_file_id = "file-3fDziK93Ez1753RgHZYyxK"

    with conn.cursor() as cur:
        # Insert batches
        cur.execute(
            """
            INSERT INTO ai._vectorizer_async_batch_q_1
            (id, status, errors, metadata, next_attempt_after)
            VALUES (%s, %s, %s, %s, now())
        """,
            (
                single_batch_id,
                "pending",
                None,
                json.dumps({"input_file_id": single_file_id}),
            ),
        )

        # Insert single chunk
        cur.execute(
            """
            INSERT INTO ai._vectorizer_async_batch_chunks_1
            (id, chunk_seq, async_batch_id, chunk)
            VALUES (%s, %s, %s, %s)
        """,
            (1, 0, single_batch_id, "post_1"),
        )

    # TODO: if we decide to delete existing embeddings here we should
    # insert some data into the store here.

    # Ensuring no OPENAI_API_KEY env set for the worker
    # to test loading secret from db
    del os.environ["OPENAI_API_KEY"]

    # When running the worker with cassette matching original test params
    cassette = (
        f"openai-character_text_splitter-chunk_value-"
        f"items={num_items}-batch_size={batch_size}-"
        "async_batch=True-fail_step=ready.yaml"
    )
    logging.getLogger("vcr").setLevel(logging.DEBUG)

    vcr_with_boundary_overwrite = vcr.VCR(
        serializer=vcr_.serializer,
        cassette_library_dir=vcr_.cassette_library_dir,
        record_mode=vcr.mode.ONCE,
        filter_headers=vcr_.filter_headers,
        match_on=vcr_.match_on,
        before_record_response=vcr_.before_record_response,
        before_record_request=rewrite_request_boundary,
    )

    with vcr_with_boundary_overwrite.use_cassette(cassette):  # type:ignore
        result = run_vectorizer_worker(cli_db_url, vectorizer_id, concurrency)

    assert result.exception
    assert "openai.NotFoundError" in result.stdout

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT id, total_attempts, status
            FROM ai._vectorizer_async_batch_q_1;
        """)
        assert cur.fetchone() == {
            "id": single_batch_id,
            "total_attempts": 1,
            "status": "pending",
        }


@pytest.mark.parametrize(
    "num_items,concurrency,batch_size",
    [
        (1, 1, 1),
    ],
)
def test_process_async_batch_fail_step_cleanup(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
    num_items: int,
    concurrency: int,
    batch_size: int,
):
    """Test successful processing of vectorizer tasks"""
    _, conn = cli_db
    vectorizer_id = configure_openai_vectorizer(
        cli_db[1],
        number_of_rows=0,  # The items are pending in the async batch.
        concurrency=concurrency,
        batch_size=batch_size,
    )

    single_batch_id = "batch_67cf68323760819097ce6ea8b3337bfa"
    single_file_id = "file-3fDziK93Ez1753RgHZYyxK"

    with conn.cursor() as cur:
        # Insert batches
        cur.execute(
            """
            INSERT INTO ai._vectorizer_async_batch_q_1
            (id, status, errors, metadata, next_attempt_after)
            VALUES (%s, %s, %s, %s, now())
        """,
            (
                single_batch_id,
                "pending",
                None,
                json.dumps({"input_file_id": single_file_id}),
            ),
        )

        # Insert single chunk
        cur.execute(
            """
            INSERT INTO ai._vectorizer_async_batch_chunks_1
            (id, chunk_seq, async_batch_id, chunk)
            VALUES (%s, %s, %s, %s)
        """,
            (1, 0, single_batch_id, "post_1"),
        )

    # TODO: if we decide to delete existing embeddings here we should
    # insert some data into the store here.

    # Ensuring no OPENAI_API_KEY env set for the worker
    # to test loading secret from db
    del os.environ["OPENAI_API_KEY"]

    # When running the worker with cassette matching original test params
    cassette = (
        f"openai-character_text_splitter-chunk_value-"
        f"items={num_items}-batch_size={batch_size}-"
        "async_batch=True-fail_step=imported.yaml"
    )
    logging.getLogger("vcr").setLevel(logging.DEBUG)

    vcr_with_boundary_overwrite = vcr.VCR(
        serializer=vcr_.serializer,
        cassette_library_dir=vcr_.cassette_library_dir,
        record_mode=vcr.mode.NEW_EPISODES,
        filter_headers=vcr_.filter_headers,
        match_on=vcr_.match_on,
        before_record_response=vcr_.before_record_response,
        before_record_request=rewrite_request_boundary,
    )

    with vcr_with_boundary_overwrite.use_cassette(cassette):  # type:ignore
        result = run_vectorizer_worker(cli_db_url, vectorizer_id, concurrency)

    assert result.exception
    assert "openai.NotFoundError" in result.stdout

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, total_attempts, status FROM ai._vectorizer_async_batch_q_1;"
        )
        assert cur.fetchone() == {
            "id": single_batch_id,
            "total_attempts": 1,
            "status": "imported",
        }
        cur.execute("SELECT count(*) as count FROM blog_embedding_store;")
        assert cur.fetchone()["count"] == num_items  # type: ignore
        cur.execute("SELECT count(*) as count FROM ai._vectorizer_q_1;")
        assert cur.fetchone()["count"] == 0  # type: ignore
        cur.execute(
            "SELECT count(*) as count FROM ai._vectorizer_async_batch_chunks_1;"
        )
        assert cur.fetchone()["count"] == 0  # type: ignore


@pytest.mark.parametrize(
    "num_items,concurrency,batch_size",
    [
        (1, 1, 1),
    ],
)
def test_process_async_batch_do_cleanup_if_already_imported(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
    num_items: int,
    concurrency: int,
    batch_size: int,
):
    """Test successful processing of vectorizer tasks"""
    _, conn = cli_db
    vectorizer_id = configure_openai_vectorizer(
        cli_db[1],
        number_of_rows=0,  # The items are pending in the async batch.
        concurrency=concurrency,
        batch_size=batch_size,
    )

    single_batch_id = "batch_67cf68323760819097ce6ea8b3337bfa"
    single_file_id = "file-3fDziK93Ez1753RgHZYyxK"
    output_file_id = "file-QNbJfuphnZ9E6AVfSizc9V"

    with conn.cursor() as cur:
        # Insert batches
        cur.execute(
            """
            INSERT INTO ai._vectorizer_async_batch_q_1
            (id, status, errors, metadata, next_attempt_after)
            VALUES (%s, %s, %s, %s, now())
        """,
            (
                single_batch_id,
                "imported",
                None,
                json.dumps(
                    {
                        "input_file_id": single_file_id,
                        "output_file_id": output_file_id,
                        "error_file_id": None,
                    }
                ),
            ),
        )

        # Insert single chunk
        cur.execute(
            """
            INSERT INTO ai._vectorizer_async_batch_chunks_1
            (id, chunk_seq, async_batch_id, chunk)
            VALUES (%s, %s, %s, %s)
        """,
            (1, 0, single_batch_id, "post_1"),
        )

    # TODO: if we decide to delete existing embeddings here we should
    # insert some data into the store here.

    # Ensuring no OPENAI_API_KEY env set for the worker
    # to test loading secret from db
    del os.environ["OPENAI_API_KEY"]

    # When running the worker with cassette matching original test params
    cassette = (
        f"openai-character_text_splitter-chunk_value-"
        f"items={num_items}-batch_size={batch_size}-"
        "async_batch=True-status=imported.yaml"
    )
    logging.getLogger("vcr").setLevel(logging.DEBUG)

    vcr_with_boundary_overwrite = vcr.VCR(
        serializer=vcr_.serializer,
        cassette_library_dir=vcr_.cassette_library_dir,
        record_mode=vcr.mode.ONCE,
        filter_headers=vcr_.filter_headers,
        match_on=vcr_.match_on,
        before_record_response=vcr_.before_record_response,
        before_record_request=rewrite_request_boundary,
    )

    with vcr_with_boundary_overwrite.use_cassette(cassette):  # type:ignore
        result = run_vectorizer_worker(cli_db_url, vectorizer_id, concurrency)

    assert not result.exception

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) FROM ai._vectorizer_async_batch_q_1;")
        assert cur.fetchone()["count"] == 0  # type: ignore
        # The embeddings store was not touched.
        cur.execute("SELECT count(*) as count FROM blog_embedding_store;")
        assert cur.fetchone()["count"] == 0  # type: ignore
        cur.execute("SELECT count(*) as count FROM ai._vectorizer_q_1;")
        assert cur.fetchone()["count"] == 0  # type: ignore
        cur.execute(
            "SELECT count(*) as count FROM ai._vectorizer_async_batch_chunks_1;"
        )
        assert cur.fetchone()["count"] == 0  # type: ignore


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
        chunking="chunking_recursive_character_text_splitter('content')",
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
