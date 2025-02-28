import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from pgai.vectorizer.loading import DocumentLoadingError
from tests.vectorizer.cli.conftest import (
    TestDatabase,
    configure_vectorizer,
    run_vectorizer_worker,
)

docs = [
    "Sacred Texts of PostgreSQL.pdf",
    "sample_pdf.pdf",
    "sample_with_table.pdf",
    "sample_txt.txt",
    "basic-v3plus2.epub",
    "test.md",
    "lego_sets.pdf",
]


def setup_documents_table(
    connection: Connection,
    number_of_rows: int,
    base_path: Path | str,
    documents: list[str],
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
            doc_index = (i - 1) % len(documents)
            s3_url = str(base_path) + "/" + documents[doc_index]
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
    loading: str = "ai.loading_uri(column_name => 'url')",
    parsing: str = "ai.parsing_auto()",
    chunking: str = "chunking_recursive_character_text_splitter(chunk_size => 700,"
    # ' | ' is a separator for the md table extracted from lego_sets.pdf
    # otherwise we reach max token length
    "separators => array[E'\n\n', E'\n', '.', '?', '!', ' ', '', ' | '])",
    formatting: str = "formatting_python_template('$chunk')",
    documents: list[str] | None = None,
) -> int:
    """Creates and configures a vectorizer for testing"""
    if documents is None:
        documents = docs
    documents_table = setup_documents_table(
        connection, number_of_rows, base_path, documents
    )
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
        loading=loading,
        parsing=parsing,
    )


def test_simple_document_embedding_local(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that a document is successfully embedded"""
    connection = cli_db[1]
    vectorizer_id = configure_document_vectorizer(cli_db[1], number_of_rows=len(docs))

    # Huggingface.co hosts is being ignored globally.
    # Docling will download its models if not found.
    with vcr_.use_cassette("simple-docs.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    if result.exception:
        print(result.stdout)

    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as errors FROM ai.vectorizer_errors;")
        assert cur.fetchone()["errors"] == 0  # type: ignore

        cur.execute("SELECT count(*) as count FROM documents_embedding_store;")
        assert cur.fetchone()["count"] > len(docs)  # type: ignore

        cur.execute("SELECT chunk FROM documents_embedding_store;")
        chunks = cur.fetchall()
        chunks_str = "\n".join([chunk["chunk"] for chunk in chunks])

        # Sacred Texts of PostgreSQL.pdf
        assert "And lo, there came forth PostgreSQL, blessed be its name" in chunks_str

        # sample_pdf.pdf
        assert "Maecenas mauris lectus" in chunks_str

        # sample_with_table.pdf
        assert "This is an example of a data table." in chunks_str

        # sample_txt.txt
        assert "Fromage frais cheese and biscuits danish fontina" in chunks_str

        # basic-v3plus2.epub
        # epub is not supported by docling but by pymupdf. auto parser handles this.
        assert "Wants pawn term dare worsted ladle gull hoe lift" in chunks_str

        # test.md
        assert "Hello I am a test md document" in chunks_str

        # lego_sets.pdf
        assert "7190-1 Millennium Falcon" in chunks_str


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

    # This is necessary to prevent boto3 from using the default credentials file.
    os.environ["AWS_SHARED_CREDENTIALS_FILE"] = "/dev/null"

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

    # required for accessing this S3 bucket in particular
    os.environ["AWS_DEFAULT_REGION"] = "eu-central-1"

    # This is necessary to prevent boto3 from pulling credentials
    # from WS Instance Metadata Service when those are missing.
    # Comment if you need to recreate the cassette.
    os.environ["AWS_ACCESS_KEY_ID"] = "FAKE"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "FAKE"
    os.environ["AWS_SHARED_CREDENTIALS_FILE"] = "/dev/null"

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


def test_binary_document_embedding(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that a document stored as binary data is successfully embedded"""
    connection = cli_db[1]

    # Create a table with bytea column
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            CREATE TABLE binary_documents (
                id INT NOT NULL PRIMARY KEY,
                byte_content BYTEA NOT NULL
            )
        """)

        # Read PDF files and insert as binary
        base_path = Path(__file__).parent / "documents"
        values: list[tuple[int, bytes]] = []
        for i, doc in enumerate(docs, start=1):
            if doc.endswith(".pdf"):  # Only process PDF files
                file_path = base_path / doc
                with open(file_path, "rb") as f:
                    binary_content = f.read()
                values.append((i, binary_content))

        cur.executemany(
            "INSERT INTO binary_documents (id, byte_content) VALUES (%s, %s)", values
        )

    # Configure vectorizer with binary loading
    vectorizer_id = configure_vectorizer(
        "binary_documents",
        connection,
        loading="ai.loading_column(column_name => 'byte_content')",
        parsing="ai.parsing_auto()",
        chunking="chunking_character_text_splitter()",
        formatting="formatting_python_template('$chunk')",
    )

    with vcr_.use_cassette("binary-docs.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    if result.exception:
        print(result.stdout)

    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as count FROM binary_documents_embedding_store;")
        count = cur.fetchone()["count"]  # type: ignore
        assert count > 0  # We should have some chunks

        cur.execute("SELECT chunk FROM binary_documents_embedding_store;")
        chunks = cur.fetchall()
        chunks_str = "\n".join([chunk["chunk"] for chunk in chunks])

        # Verify content from PDFs was processed
        assert (
            "And lo, there came forth PostgreSQL, blessed be its name" in chunks_str
        )  # From Sacred Texts
        assert "Maecenas mauris lectus" in chunks_str  # From sample_pdf
        assert (
            "This is an example of a data table." in chunks_str
        )  # From sample_with_table


def test_retries_on_not_present_document_embedding_s3(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that embedding documents are successfully retried"""
    connection = cli_db[1]
    vectorizer_id = configure_document_vectorizer(
        cli_db[1], base_path="s3://adol-docs-test", documents=["non_existing_doc.pdf"]
    )

    with vcr_.use_cassette("doc_retries_s3_not_found.yaml"):
        try:
            run_vectorizer_worker(cli_db_url, vectorizer_id)
        except DocumentLoadingError as e:
            assert e.msg == "document loading failed"

    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) FROM ai._vectorizer_q_1;")
        assert cur.fetchone()["count"] == 1  # type: ignore
        cur.execute("SELECT id, message, details FROM ai.vectorizer_errors")
        records = cur.fetchall()
        assert len(records) == 1
        error = records[0]
        assert error["id"] == vectorizer_id
        assert error["message"] == "document loading failed"
        assert error["details"] == {
            "loader": "document",
            "error_reason": "unable to access bucket: 'adol-docs-test'"
            " key: 'non_existing_doc.pdf' version: None"
            " error: An error occurred (NoSuchKey) when"
            " calling the GetObject operation: The specified"
            " key does not exist.",
            "is_retryable": True,
        }

        cur.execute("SELECT retries, retry_after FROM ai._vectorizer_q_1;")
        queue_item = cur.fetchone()
        assert queue_item["retries"] == 1  # type: ignore
        assert queue_item["retry_after"] > datetime.now(tz=timezone.utc)  # type: ignore


def test_no_more_retries_after_six_failures(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that embedding documents are successfully retried"""
    connection = cli_db[1]
    vectorizer_id = configure_document_vectorizer(
        cli_db[1], base_path="s3://adol-docs-test", documents=["non_existing_doc.pdf"]
    )

    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "UPDATE ai._vectorizer_q_1"
            " SET retries=6, retry_after=now() - interval '1 minute';"
        )
        cur.execute("SELECT retries, retry_after FROM ai._vectorizer_q_1;")
        queue_item = cur.fetchone()
        assert queue_item["retries"] == 6  # type: ignore
        assert queue_item["retry_after"] < datetime.now(tz=timezone.utc)  # type: ignore

    with vcr_.use_cassette("doc_retries_s3_not_found.yaml"):
        try:
            run_vectorizer_worker(
                cli_db_url, vectorizer_id, extra_params=["--loading-retries=6"]
            )
        except DocumentLoadingError as e:
            assert e.msg == "document loading failed"

    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) FROM ai._vectorizer_q_1;")
        assert cur.fetchone()["count"] == 0  # type: ignore
        cur.execute("SELECT id, message, details FROM ai.vectorizer_errors")
        records = cur.fetchall()
        assert len(records) == 1
        error = records[0]
        assert error["id"] == vectorizer_id
        assert error["message"] == "document loading failed"
        assert error["details"] == {
            "loader": "document",
            "error_reason": "unable to access bucket: 'adol-docs-test'"
            " key: 'non_existing_doc.pdf' version: None"
            " error: An error occurred (NoSuchKey) when"
            " calling the GetObject operation: The specified"
            " key does not exist.",
            "is_retryable": False,
        }

        cur.execute("SELECT count(*) FROM ai._vectorizer_q_1;")
        assert cur.fetchone()["count"] == 0  # type: ignore


def test_retries_should_do_nothing_if_retry_after_is_in_the_future(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that embedding documents are successfully retried"""
    connection = cli_db[1]
    vectorizer_id = configure_document_vectorizer(
        cli_db[1], base_path="s3://adol-docs-test", documents=["non_existing_doc.pdf"]
    )

    with vcr_.use_cassette("doc_retries_s3_not_found.yaml"):
        try:
            run_vectorizer_worker(
                cli_db_url, vectorizer_id, extra_params=["--loading-retries=6"]
            )
        except DocumentLoadingError as e:
            assert e.msg == "document loading failed"

    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) FROM ai._vectorizer_q_1;")
        assert cur.fetchone()["count"] == 1  # type: ignore
        cur.execute("SELECT id, message, details FROM ai.vectorizer_errors")
        records = cur.fetchall()
        assert len(records) == 1
        error = records[0]
        assert error["id"] == vectorizer_id
        assert error["message"] == "document loading failed"
        assert error["details"] == {
            "loader": "document",
            "error_reason": "unable to access bucket: 'adol-docs-test'"
            " key: 'non_existing_doc.pdf' version: None"
            " error: An error occurred (NoSuchKey) when"
            " calling the GetObject operation: The specified"
            " key does not exist.",
            "is_retryable": True,
        }

        cur.execute(
            "UPDATE ai._vectorizer_q_1 SET retry_after=now() + interval '10 minute';"
        )
        cur.execute("SELECT retries, retry_after FROM ai._vectorizer_q_1;")
        queue_item = cur.fetchone()
        assert queue_item["retries"] == 1  # type: ignore
        assert queue_item["retry_after"] > datetime.now(tz=timezone.utc)  # type: ignore

    with vcr_.use_cassette("doc_retries_s3_not_found.yaml"):
        try:
            run_vectorizer_worker(cli_db_url, vectorizer_id)
        except DocumentLoadingError as e:
            assert e.msg == "document loading failed"

    # Retries shouldn't have changed, given that
    # the retry_after field is in the future.
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT retries, retry_after FROM ai._vectorizer_q_1;")
        queue_item = cur.fetchone()
        assert queue_item["retries"] == 1  # type: ignore
        assert queue_item["retry_after"] > datetime.now(tz=timezone.utc)  # type: ignore
