from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from tests.vectorizer.cli.conftest import (
    TestDatabase,
    run_vectorizer_worker,
    setup_source_table,
)


def configure_same_table_vectorizer(
    connection: Connection,
    table_name: str,
) -> int:
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute(f"""
            SELECT ai.create_vectorizer(
                '{table_name}'::regclass,
                destination => ai.destination_source('embedding'),
                embedding => ai.embedding_openai('text-embedding-ada-002', 1536),
                chunking => ai.chunking_none(),
                loading => ai.loading_column('content')
            )
        """)  # type: ignore

        vectorizer_id: int = int(cur.fetchone()["create_vectorizer"])  # type: ignore
        return vectorizer_id


def test_same_table_vectorizer(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """
    Test that destination_source works and adds the embeddings to the original table
    """
    _, con = cli_db
    table_name = setup_source_table(con, 2)

    # Given a vectorizer that has 2 items and a batch size of 1
    vectorizer_id = configure_same_table_vectorizer(con, table_name)

    with vcr_.use_cassette("same_table_vectorizer.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 0
    assert "finished processing vectorizer" in result.output.lower()

    with con.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM blog;")
        results = cur.fetchone()
        assert results is not None
        assert results["embedding"] is not None
