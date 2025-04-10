import pytest
from psycopg import Connection
from psycopg.rows import dict_row

from tests.vectorizer.cli.conftest import (
    TestDatabase,
    configure_vectorizer,
    run_vectorizer_worker,
    setup_source_table,
)


@pytest.mark.parametrize(
    "column_def",
    [
        "new_column text",
        "new_column text NOT NULL DEFAULT 'default_value'",
    ],
)
def test_additional_columns_are_added_to_target_table(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    column_def: str,
):
    """Test that if additional columns are added to the target table,
    the vectorizer still works"""
    _, connection = cli_db
    table_name = setup_source_table(connection, 2)
    vectorizer_id = configure_vectorizer(
        table_name,
        cli_db[1],
    )
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute(f"ALTER TABLE blog_embedding_store ADD COLUMN {column_def}")  # type: ignore

    result = run_vectorizer_worker(cli_db_url, vectorizer_id)
    print(result.stdout)
    assert result.exit_code == 0

    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM blog_embedding_store")
        rows = cur.fetchall()
        assert len(rows) == 2


def test_embedding_column_removal_and_readd(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
):
    """Test that the vectorizer still works when the embedding column is removed,
    another column is added, and then the embedding column is re-added."""
    _, connection = cli_db
    table_name = setup_source_table(connection, 2)
    vectorizer_id = configure_vectorizer(
        table_name,
        cli_db[1],
    )

    # First run to create original rows
    result = run_vectorizer_worker(cli_db_url, vectorizer_id)
    assert result.exit_code == 0

    # Check original rows were created
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM blog_embedding_store")
        rows = cur.fetchall()
        assert len(rows) == 2
        # Verify embedding column exists
        assert "embedding" in rows[0]

        # Drop View so we can change column order
        cur.execute("DROP VIEW IF EXISTS blog_embedding")

        # Remove embedding column
        cur.execute("ALTER TABLE blog_embedding_store DROP COLUMN embedding")

        # Add another optional column
        cur.execute("ALTER TABLE blog_embedding_store ADD COLUMN extra_data text")

        # Re-add embedding column with same type
        cur.execute(
            "ALTER TABLE blog_embedding_store ADD COLUMN embedding vector(1536)"
        )

        # Remove original rows
        cur.execute("DELETE FROM blog")

        # Add new rows
        values = [(i, i, f"post_{i}") for i in range(1, 3)]
        cur.executemany(
            "INSERT INTO blog(id, id2, content) VALUES (%s, %s, %s)",
            values,
        )

    # Run vectorizer again
    result = run_vectorizer_worker(cli_db_url, vectorizer_id)
    print(result.stdout)
    assert result.exit_code == 0

    # Verify vectorizer still works
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM blog_embedding_store")
        rows = cur.fetchall()
        assert len(rows) == 2
        # Verify embedding column exists and has data
        assert "embedding" in rows[0]
        assert rows[0]["embedding"] is not None
