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
