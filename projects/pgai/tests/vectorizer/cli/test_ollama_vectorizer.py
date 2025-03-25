import os
from pathlib import Path

import pytest
from psycopg import Connection
from psycopg.rows import dict_row
from testcontainers.ollama import OllamaContainer  # type: ignore
from testcontainers.postgres import PostgresContainer  # type: ignore

from tests.vectorizer.cli.conftest import (
    TestDatabase,
    configure_vectorizer,
    run_vectorizer_worker,
    setup_source_table,
)


@pytest.fixture(scope="session")
def ollama_url():
    # If the OLLAMA_HOST environment variable is set, we assume that the user
    # has an Ollama container running and we don't need to start a new one.
    if "OLLAMA_HOST" in os.environ:
        yield os.environ["OLLAMA_HOST"]
    else:
        with OllamaContainer(
            image="ollama/ollama:latest",
            # Passing the ollama_home lets us reuse models that have already
            # been pulled to the `~/.ollama` path on the host machine.
            ollama_home=Path.home() / ".ollama",
        ) as ollama:
            yield ollama.get_endpoint()


def configure_ollama_vectorizer(
    connection: Connection,
    ollama_url: str,
    number_of_rows: int = 1,
    concurrency: int = 1,
    batch_size: int = 1,
    chunking: str = "chunking_character_text_splitter()",
    formatting: str = "formatting_python_template('$chunk')",
) -> int:
    """Creates and configures an ollama vectorizer for testing"""

    table_name = setup_source_table(connection, number_of_rows)
    return configure_vectorizer(
        table_name,
        connection,
        concurrency=concurrency,
        batch_size=batch_size,
        chunking=chunking,
        formatting=formatting,
        embedding=f"embedding_ollama('nomic-embed-text',"
        f"768, base_url => '{ollama_url}')",
    )


@pytest.mark.parametrize(
    "num_items,concurrency,batch_size",
    [
        (1, 1, 1),
        (4, 2, 2),
    ],
)
def test_ollama_vectorizer(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    ollama_url: str,
    num_items: int,
    concurrency: int,
    batch_size: int,
):
    """Test successful processing of vectorizer tasks"""
    _, conn = cli_db

    vectorizer_id = configure_ollama_vectorizer(
        cli_db[1],
        ollama_url,
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
            array_fill(0, ARRAY[768])::vector)
        """)
    result = run_vectorizer_worker(cli_db_url, vectorizer_id, concurrency)

    assert not result.exception
    assert result.exit_code == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as count FROM blog_embedding_store;")
        assert cur.fetchone()["count"] == num_items  # type: ignore


@pytest.mark.parametrize(
    "chunking",
    [
        "chunking_character_text_splitter()",
        "chunking_recursive_character_text_splitter()",
    ],
)
def test_vectorization_successful_with_null_contents(
    cli_db: tuple[PostgresContainer, Connection],
    cli_db_url: str,
    ollama_url: str,
    chunking: str,
):
    _, conn = cli_db
    vectorizer_id = configure_ollama_vectorizer(conn, ollama_url, chunking=chunking)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("ALTER TABLE blog ALTER COLUMN content DROP NOT NULL;")
        cur.execute("UPDATE blog SET content = null;")

    result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert not result.exception
    assert result.exit_code == 0

    _, conn = cli_db

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as count FROM blog_embedding_store;")
        assert cur.fetchone()["count"] == 0  # type: ignore
