import os
from pathlib import Path
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from tests.vectorizer.cli.conftest import (
    TestDatabase,
    configure_vectorizer,
    run_vectorizer_worker,
)

docs = [
    "Sacred Texts of PostgreSQL.pdf",
    "sample_pdf.pdf",
    "sample_with_table.pdf",
]


def setup_documents_table(
    connection: Connection, number_of_rows: int, base_path: Path | str
):
    table_name = "documents"
    with connection.cursor(row_factory=dict_row) as cur:
        # Create source table
        cur.execute(f"""
                CREATE TABLE {table_name} (
                    id INT NOT NULL PRIMARY KEY,
                    url TEXT NOT NULL
                )
            """)

        values: list[tuple[int, str]] = []
        for i in range(1, number_of_rows + 1):
            doc_index = (i - 1) % len(docs)
            s3_url = str(base_path) + "/" + docs[doc_index]
            values.append((i, str(s3_url)))

        cur.executemany("INSERT INTO documents (id, url) VALUES (%s, %s)", values)
    return table_name


def configure_document_vectorizer(
    connection: Connection,
    openai_proxy_url: str | None = None,
    number_of_rows: int = 1,
    concurrency: int = 1,
    batch_size: int = 1,
    base_path: Path | str = Path(__file__).parent / "documents",
    chunking: str = "chunking_character_text_splitter()",
    formatting: str = "formatting_python_template('$chunk')",
    loader: str = "ai.loader_from_document(file_uri_column => 'url')",
    parser: str = "ai.parser_auto()",
) -> int:
    """Creates and configures a vectorizer for testing"""
    documents_table = setup_documents_table(connection, number_of_rows, base_path)
    base_url = (
        f", base_url => '{openai_proxy_url}'" if openai_proxy_url is not None else ""
    )
    embedding = f"embedding_openai('text-embedding-ada-002', 1536{base_url})"
    return configure_vectorizer(
        documents_table,
        connection,
        concurrency=concurrency,
        batch_size=batch_size,
        chunking=chunking,
        formatting=formatting,
        embedding=embedding,
        loader=loader,
        parser=parser,
    )


def test_simple_document_embedding_local(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that a document is successfully embedded"""
    connection = cli_db[1]
    vectorizer_id = configure_document_vectorizer(cli_db[1])

    with vcr_.use_cassette("simple-docs.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    if result.exception:
        print(result.stdout)

    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as count FROM documents_embedding_store;")
        assert cur.fetchone()["count"] > 0  # type: ignore
        cur.execute("SELECT chunk FROM documents_embedding_store;")
        chunks = cur.fetchall()
        chunks_str = "\n".join([chunk["chunk"] for chunk in chunks])
        assert "And lo, there came forth PostgreSQL, blessed be its name" in chunks_str


def test_simple_document_embedding_s3_no_credentials(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
):
    """Test that embedding fails when no credentials are available"""
    vectorizer_id = configure_document_vectorizer(
        cli_db[1], base_path="s3://adol-docs-test"
    )
    if "AWS_ACCESS_KEY_ID" in os.environ:
        del os.environ["AWS_ACCESS_KEY_ID"]
    if "AWS_SECRET_ACCESS_KEY" in os.environ:
        del os.environ["AWS_SECRET_ACCESS_KEY"]
    # No cassette because it should never get to an API call.
    result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 1
    assert "Unable to locate credentials" in result.stdout


def test_simple_document_embedding_s3(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that a document is successfully embedded"""
    connection = cli_db[1]
    vectorizer_id = configure_document_vectorizer(
        cli_db[1], base_path="s3://adol-docs-test"
    )
    os.environ["AWS_ACCESS_KEY_ID"] = "FAKE"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "FAKE"

    with vcr_.use_cassette("simple-s3-docs.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    if result.exception:
        print(result.stdout)

    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as count FROM documents_embedding_store;")
        assert cur.fetchone()["count"] > 0  # type: ignore
        cur.execute("SELECT chunk FROM documents_embedding_store;")
        chunks = cur.fetchall()
        chunks_str = "\n".join([chunk["chunk"] for chunk in chunks])
        assert "And lo, there came forth PostgreSQL, blessed be its name" in chunks_str
