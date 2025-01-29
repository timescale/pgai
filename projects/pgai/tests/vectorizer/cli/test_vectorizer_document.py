import os

from dotenv import load_dotenv
from psycopg import Connection
from psycopg.rows import dict_row

from tests.vectorizer.cli.conftest import (
    TestDatabase,
    configure_vectorizer,
    run_vectorizer_worker,
)

load_dotenv()

s3_base = os.environ["S3_BASE_URL"]
docs = [
    "sample_pdf.pdf",
    "sample_with_table.pdf",
    "stop recommending clean code.pdf",
    "stop_recommending_clean_code.pdf",
    "stop_recommending_clean_code.txt",
]


def setup_documents_table(connection: Connection, number_of_rows: int):
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
            s3_url = s3_base + docs[doc_index]
            values.append((i, s3_url))

        cur.executemany("INSERT INTO documents (id, url) VALUES (%s, %s)", values)
    return table_name


def configure_document_vectorizer(
    connection: Connection,
    openai_proxy_url: str | None = None,
    number_of_rows: int = 1,
    concurrency: int = 1,
    batch_size: int = 1,
    chunking: str = "chunking_character_text_splitter()",
    formatting: str = "formatting_python_template('$chunk')",
) -> int:
    """Creates and configures a vectorizer for testing"""
    documents_table = setup_documents_table(connection, number_of_rows)
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
        loader="ai.loader_s3(url_column => 'url')",  # this could also just be ai.file_loader() ?
        parser="ai.parser_pymupdf()",
    )


def test_simple_document_embedding(
    cli_db: tuple[TestDatabase, Connection], cli_db_url: str
):
    """Test that a document is successfully embedded"""
    connection = cli_db[1]
    setup_documents_table(connection, 1)
    vectorizer_id = configure_document_vectorizer(cli_db[1])

    run_vectorizer_worker(cli_db_url, vectorizer_id)

    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as count FROM documents_embedding_store;")
        assert cur.fetchone()["count"] > 0  # type: ignore
