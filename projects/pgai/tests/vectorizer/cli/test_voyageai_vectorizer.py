import logging
import os
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import dict_row

from tests.vectorizer.cli.conftest import (
    TestDatabase,
    configure_vectorizer,
    run_vectorizer_worker,
    setup_source_table,
)


def configure_voyageai_vectorizer_id(
    connection: Connection,
    number_of_rows: int = 1,
    concurrency: int = 1,
    batch_size: int = 1,
    chunking: str = "chunking_character_text_splitter()",
    formatting: str = "formatting_python_template('$chunk')",
) -> int:
    """Creates and configures a VoyageAI vectorizer for testing"""

    table_name = setup_source_table(connection, number_of_rows)
    return configure_vectorizer(
        table_name,
        connection,
        concurrency=concurrency,
        batch_size=batch_size,
        chunking=chunking,
        formatting=formatting,
        embedding="embedding_voyageai('voyage-3-lite', 512)",
    )


@pytest.mark.parametrize(
    "num_items,concurrency,batch_size",
    [
        (1, 1, 1),
        (4, 2, 2),
    ],
)
def test_voyageai_vectorizer(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
    num_items: int,
    concurrency: int,
    batch_size: int,
):
    """Test successful processing of vectorizer tasks"""
    if "VOYAGE_API_KEY" not in os.environ:
        os.environ["VOYAGE_API_KEY"] = "A FAKE KEY"
    _, conn = cli_db
    vectorizer_id = configure_voyageai_vectorizer_id(
        cli_db[1],
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
            array_fill(0, ARRAY[512])::vector)
        """)

    # When running the worker with cassette matching original test params
    cassette = (
        f"voyageai-character_text_splitter-chunk_value-"
        f"items={num_items}-batch_size={batch_size}.yaml"
    )
    logging.getLogger("vcr").setLevel(logging.DEBUG)
    with vcr_.use_cassette(cassette):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id, concurrency)

    assert not result.exception
    assert result.exit_code == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as count FROM blog_embedding_store;")
        assert cur.fetchone()["count"] == num_items  # type: ignore


def test_voyageai_vectorizer_fails_when_api_key_is_not_set(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
):
    """Test missing API Key"""
    _, conn = cli_db

    # Ensure API key env var is not set.
    if "VOYAGE_API_KEY" in os.environ:
        del os.environ["VOYAGE_API_KEY"]

    # Set up vectorizer which will fail to embed chunk
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("CREATE TABLE blog(id bigint primary key, content text);")
        cur.execute("""SELECT ai.create_vectorizer(
                'blog',
                loading => ai.loading_column('content'),
                embedding => ai.embedding_voyageai(
                    'voyage-3-lite',
                    512
                ),
                chunking => ai.chunking_character_text_splitter()
        )""")  # noqa
        cur.execute("INSERT INTO blog (id, content) VALUES(1, repeat('1', 100000))")

    result = run_vectorizer_worker(cli_db_url)

    assert result.exit_code == 1
    assert "ApiKeyNotFoundError" in result.output
