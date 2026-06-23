"""Integration tests for BM25 text indexing in vectorizers.

Tests verify that the text_indexing parameter works correctly with pg_textsearch.
"""

from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import dict_row

from tests.vectorizer.cli.conftest import (
    TestDatabase,
    run_vectorizer_worker,
    setup_source_table,
)


def configure_vectorizer_with_text_indexing(
    connection: Connection,
    table_name: str,
    text_indexing: str | None = None,
    chunking: str = "chunking_recursive_character_text_splitter(128, 10)",
) -> int:
    """Creates a vectorizer with optional text_indexing configuration."""
    text_indexing_clause = (
        f", text_indexing => ai.{text_indexing}" if text_indexing else ""
    )

    with connection.cursor(row_factory=dict_row) as cur:
        # Ensure pg_textsearch extension is created if text_indexing uses bm25
        if text_indexing and "bm25" in text_indexing:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_textsearch CASCADE")

        cur.execute(f"""
            SELECT ai.create_vectorizer(
                '{table_name}'::regclass,
                loading => ai.loading_column('content'),
                embedding => ai.embedding_openai('text-embedding-ada-002', 1536),
                chunking => ai.{chunking},
                formatting => ai.formatting_python_template('$chunk'),
                processing => ai.processing_default(batch_size => 1, concurrency => 1)
                {text_indexing_clause}
            )
        """)  # type: ignore[arg-type]
        return int(cur.fetchone()["create_vectorizer"])  # type: ignore


def test_text_indexing_creates_bm25_index(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that BM25 index is created on chunk column when text_indexing is enabled."""
    _, conn = cli_db
    table_name = setup_source_table(conn, number_of_rows=3)

    vectorizer_id = configure_vectorizer_with_text_indexing(
        conn,
        table_name,
        text_indexing="text_indexing_bm25()",
    )

    # Run worker
    with vcr_.use_cassette("text_indexing_creates_bm25_index.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 0

    # Verify BM25 index exists on the embedding table's chunk column
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT indexname, tablename, indexdef FROM pg_indexes
            WHERE indexdef ILIKE '%using bm25%'
        """)
        index = cur.fetchone()
        assert index is not None, "BM25 index should have been created"
        assert (
            "chunk" in index["indexdef"].lower()
        ), "BM25 index should be on chunk column"
        assert (
            "blog_embedding" in index["tablename"] or "embedding" in index["tablename"]
        ), f"BM25 index should be on embedding table, got {index['tablename']}"


def test_text_indexing_enables_fulltext_search(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that BM25 search queries work after vectorizer creates index."""
    _, conn = cli_db

    # Create table with specific content for search testing
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE search_docs (
                id SERIAL PRIMARY KEY,
                id2 INT NOT NULL DEFAULT 1,
                content TEXT NOT NULL
            )
        """)
        cur.execute("""
            INSERT INTO search_docs (content) VALUES
                ('PostgreSQL is a powerful relational database system'),
                ('Machine learning models require large training datasets'),
                ('Python programming language is popular for data science')
        """)

    vectorizer_id = configure_vectorizer_with_text_indexing(
        conn,
        "search_docs",
        text_indexing="text_indexing_bm25(text_config => 'english')",
    )

    # Run worker
    with vcr_.use_cassette("text_indexing_enables_fulltext_search.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 0

    # Get index name for BM25 query
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT indexname FROM pg_indexes
            WHERE indexdef ILIKE '%using bm25%'
        """)
        index_row = cur.fetchone()
        assert index_row is not None
        index_name = index_row["indexname"]

        # Perform BM25 search - the <@> operator returns negative scores
        # where more negative = better match
        cur.execute(f"""
            SELECT chunk, chunk <@> to_bm25query('PostgreSQL database', '{index_name}') as score
            FROM search_docs_embedding_store
            ORDER BY chunk <@> to_bm25query('PostgreSQL database', '{index_name}')
            LIMIT 3
        """)  # type: ignore[arg-type]
        results = cur.fetchall()

        # Should have results and the PostgreSQL document should rank well
        assert len(results) > 0
        # The first result should contain our search terms or related content
        assert any(
            "postgresql" in r["chunk"].lower() or "database" in r["chunk"].lower()
            for r in results
        )


def test_text_indexing_source_column_with_chunking_none(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that BM25 index is created on source column when chunking=none."""
    _, conn = cli_db

    # Create a table with short content that doesn't need chunking
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE short_docs (
                id SERIAL PRIMARY KEY,
                id2 INT NOT NULL DEFAULT 1,
                content TEXT NOT NULL
            )
        """)
        cur.execute("""
            INSERT INTO short_docs (content) VALUES
                ('Short document one'),
                ('Short document two')
        """)

    vectorizer_id = configure_vectorizer_with_text_indexing(
        conn,
        "short_docs",
        text_indexing="text_indexing_bm25()",
        chunking="chunking_none()",
    )

    # Run worker
    with vcr_.use_cassette("text_indexing_source_column.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 0

    # Verify BM25 index is on source table's content column, not embedding table
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT tablename, indexdef FROM pg_indexes
            WHERE indexdef ILIKE '%using bm25%'
        """)
        index = cur.fetchone()
        assert index is not None, "BM25 index should have been created"
        # When chunking=none, index should be on the source table
        assert (
            index["tablename"] == "short_docs"
        ), f"Expected index on source table, got {index['tablename']}"
        assert "content" in index["indexdef"].lower()


def test_text_indexing_custom_parameters(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that custom k1, b, text_config parameters are stored in config."""
    _, conn = cli_db
    table_name = setup_source_table(conn, number_of_rows=2)

    vectorizer_id = configure_vectorizer_with_text_indexing(
        conn,
        table_name,
        text_indexing="text_indexing_bm25(text_config => 'simple', k1 => 1.5, b => 0.8)",
    )

    # Verify the custom parameters are stored in the vectorizer config
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT config->'text_indexing' as text_indexing
            FROM ai.vectorizer
            WHERE id = %s
        """,
            (vectorizer_id,),
        )
        row = cur.fetchone()
        assert row is not None
        text_indexing_config = row["text_indexing"]
        assert text_indexing_config["implementation"] == "bm25"
        assert text_indexing_config["text_config"] == "simple"
        assert float(text_indexing_config["k1"]) == 1.5
        assert float(text_indexing_config["b"]) == 0.8

    # Run worker
    with vcr_.use_cassette("text_indexing_custom_parameters.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 0

    # Verify index was created
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT indexdef FROM pg_indexes
            WHERE indexdef ILIKE '%using bm25%'
        """)
        index = cur.fetchone()
        assert index is not None, "BM25 index should have been created"


def test_text_indexing_disabled_by_default(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that no BM25 index is created when text_indexing is not specified."""
    _, conn = cli_db
    table_name = setup_source_table(conn, number_of_rows=2)

    # Create vectorizer WITHOUT text_indexing parameter
    vectorizer_id = configure_vectorizer_with_text_indexing(
        conn,
        table_name,
        text_indexing=None,  # No text indexing
    )

    # Run worker
    with vcr_.use_cassette("text_indexing_disabled_by_default.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 0

    # Verify NO BM25 index exists
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT count(*) as count FROM pg_indexes
            WHERE indexdef ILIKE '%using bm25%'
        """)
        row = cur.fetchone()
        assert row is not None
        assert row["count"] == 0, "No BM25 index should have been created"


def test_text_indexing_none_explicitly_disabled(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that text_indexing_none() explicitly disables BM25 indexing."""
    _, conn = cli_db
    table_name = setup_source_table(conn, number_of_rows=2)

    # Create vectorizer with text_indexing=none explicitly
    vectorizer_id = configure_vectorizer_with_text_indexing(
        conn,
        table_name,
        text_indexing="text_indexing_none()",
    )

    # Verify the config has implementation=none
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT config->'text_indexing' as text_indexing
            FROM ai.vectorizer
            WHERE id = %s
        """,
            (vectorizer_id,),
        )
        row = cur.fetchone()
        assert row is not None
        assert row["text_indexing"]["implementation"] == "none"

    # Run worker
    with vcr_.use_cassette("text_indexing_none_explicitly_disabled.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 0

    # Verify NO BM25 index exists
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT count(*) as count FROM pg_indexes
            WHERE indexdef ILIKE '%using bm25%'
        """)
        row = cur.fetchone()
        assert row is not None
        assert row["count"] == 0


@pytest.mark.skip(reason="Requires container without pg_textsearch extension")
def test_text_indexing_missing_extension_error(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
):
    """Test that clear error is raised when pg_textsearch is not installed.

    This test is skipped as it requires a separate container without pg_textsearch.
    The error behavior is tested at the SQL level.
    """
