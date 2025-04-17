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
                destination => ai.destination_column('embedding'),
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
    Test that destination_column works and adds the embeddings to the original table
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

        with con.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id, embedding FROM blog order by id;")
            results_pre_update = cur.fetchall()

            cur.execute("UPDATE blog set content = 'new content' where id = 1;")
            con.commit()
            result = run_vectorizer_worker(cli_db_url, vectorizer_id)
            assert result.exit_code == 0

            cur.execute("SELECT id, embedding FROM blog order by id;")
            results_post_update = cur.fetchall()

            assert (
                results_post_update[0]["embedding"]
                != results_pre_update[0]["embedding"]
            )
            assert (
                results_post_update[1]["embedding"]
                == results_pre_update[1]["embedding"]
            )

            cur.execute("SELECT * FROM ai.vectorizer_status;")
            row = cur.fetchone()
            assert row is not None
            assert row["source_table"] == "public" + "." + table_name
            assert row["target_table"] is None
            assert row["view"] is None
            assert row["embedding_column"] == "embedding"
            assert row["pending_items"] == 0
            assert not row["disabled"]

            # Check deletes just work
            cur.execute("DELETE FROM blog where id = 1;")
            con.commit()
            result = run_vectorizer_worker(cli_db_url, vectorizer_id)
            assert result.exit_code == 0
