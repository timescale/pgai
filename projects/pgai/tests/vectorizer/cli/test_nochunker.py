from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row
from testcontainers.postgres import PostgresContainer  # type: ignore

from tests.vectorizer.cli.conftest import (
    configure_vectorizer,
    run_vectorizer_worker,
    setup_source_table,
)


def test_nochunker_whole_document(
    cli_db: tuple[PostgresContainer, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that NoChunker correctly returns the entire document as a single chunk"""
    _, connection = cli_db
    table_name = setup_source_table(connection, 2)
    vectorizer_id = configure_vectorizer(
        table_name,
        cli_db[1],
        batch_size=2,
        chunking="chunking_none('content')",
    )

    # Given content of different lengths
    sample_content = """This is a longer document with multiple sentences.
    It should still be treated as a single chunk regardless of length.
    No splitting should occur even with line breaks and paragraphs.

    Second paragraph with more content."""

    shorter_content = "This is a shorter post."

    # Update the test data
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("UPDATE blog SET content = %s WHERE id = 1", (sample_content,))
        cur.execute("UPDATE blog SET content = %s WHERE id = 2", (shorter_content,))

    # When running the worker
    with vcr_.use_cassette("test_nochunker_whole_document.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 0

    # Then verify each document is a single chunk
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT id, chunk_seq, chunk
            FROM blog_embedding_store
            ORDER BY id, chunk_seq
        """)
        chunks = cur.fetchall()

        # Verify every document is a single chunk
        doc1_chunks = [c for c in chunks if c["id"] == 1]
        assert len(doc1_chunks) == 1, "Long document should be a single chunk"
        assert doc1_chunks[0]["chunk"] == sample_content, "Chunk should be the entire content"
        assert doc1_chunks[0]["chunk_seq"] == 0, "Sequence should be 0 for single chunk"

        doc2_chunks = [c for c in chunks if c["id"] == 2]
        assert len(doc2_chunks) == 1, "Short document should be a single chunk"
        assert doc2_chunks[0]["chunk"] == shorter_content, "Chunk should be the entire content"
        assert doc2_chunks[0]["chunk_seq"] == 0, "Sequence should be 0 for single chunk"


def test_nochunker_edge_cases(
    cli_db: tuple[PostgresContainer, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test NoChunker with edge cases like empty content"""
    _, connection = cli_db
    table_name = setup_source_table(connection, 3)
    vectorizer_id = configure_vectorizer(
        table_name,
        cli_db[1],
        batch_size=3,
        chunking="chunking_none('content')",
    )

    # Edge cases: empty content, very large content, content with special chars
    empty_content = ""
    large_content = "A" * 10000  # A long string
    special_content = "Content with special chars: !@#$%^&*()_+{}[]|'\";:<>?,./"

    # Update the test data
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("UPDATE blog SET content = %s WHERE id = 1", (empty_content,))
        cur.execute("UPDATE blog SET content = %s WHERE id = 2", (large_content,))
        cur.execute("UPDATE blog SET content = %s WHERE id = 3", (special_content,))

    # When running the worker
    with vcr_.use_cassette("test_nochunker_edge_cases.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 0

    # Then verify the chunking behavior on edge cases
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT id, chunk_seq, chunk
            FROM blog_embedding_store
            ORDER BY id, chunk_seq
        """)
        chunks = cur.fetchall()

        # For empty content, we should have no chunks
        empty_doc_chunks = [c for c in chunks if c["id"] == 1]
        assert len(empty_doc_chunks) == 0, "Empty document should produce no chunks"

        # For large content, we should still have one chunk
        large_doc_chunks = [c for c in chunks if c["id"] == 2]
        assert len(large_doc_chunks) == 1, "Large document should be a single chunk"
        assert large_doc_chunks[0]["chunk"] == large_content, "Chunk should be the entire content"

        # For special content, we should have one chunk with all special chars preserved
        special_doc_chunks = [c for c in chunks if c["id"] == 3]
        assert len(special_doc_chunks) == 1, "Document with special chars should be a single chunk"
        assert special_doc_chunks[0]["chunk"] == special_content, "Chunk should preserve special chars"