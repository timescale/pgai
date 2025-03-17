from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row

from tests.vectorizer.cli.conftest import (
    TestDatabase,
    configure_vectorizer,
    run_vectorizer_worker,
    setup_source_table,
    setup_source_table_composed_primary_key,
)


def configure_same_table_vectorizer(
    connection: Connection,
    number_of_rows: int = 1,
    embedding_column: str = "embedding",
) -> int:
    """Creates and configures a vectorizer for testing"""
    table_name = setup_source_table(connection, number_of_rows=number_of_rows)
    return configure_vectorizer(
        table_name, connection, skip_chunking=True, embedding_column=embedding_column
    )


def test_process_vectorizer(
    cli_db: tuple[TestDatabase, Connection], cli_db_url: str, vcr_: Any
):
    """Test successful processing of vectorizer tasks"""
    _, conn = cli_db
    vectorizer_id = configure_same_table_vectorizer(cli_db[1])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT embedding FROM blog where id='1' and id2='1';")
        result = cur.fetchone()
        assert result is not None
        assert result["embedding"] is None

    cassette = "same-table-vectorizer.yaml"
    with vcr_.use_cassette(cassette):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)
    if result.exception:
        print(f"result: {result.stdout}")
        raise result.exception
    assert not result.exception
    assert result.exit_code == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT embedding FROM blog where id='1' and id2='1';")
        result = cur.fetchone()
        assert result is not None
        assert result["embedding"] is not None


def test_process_vectorizer_composed_primary_key(
    cli_db: tuple[TestDatabase, Connection], cli_db_url: str, vcr_: Any
):
    _, conn = cli_db
    table_name = setup_source_table_composed_primary_key(conn, number_of_rows=1)
    vectorizer_id = configure_vectorizer(
        table_name,
        conn,
        skip_chunking=True,
    )

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT embedding FROM blog where id='1' and id2='1';")
        result = cur.fetchone()
        assert result is not None
        assert result["embedding"] is None

    cassette = "same-table-vectorizer.yaml"
    with vcr_.use_cassette(cassette):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)
    if result.exception:
        print(f"result: {result.stdout}")
        raise result.exception
    assert not result.exception
    assert result.exit_code == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT embedding FROM blog where id='1' and id2='1';")
        result = cur.fetchone()
        assert result is not None
        assert result["embedding"] is not None


def test_multiple_rows_vectorizer(
    cli_db: tuple[TestDatabase, Connection], cli_db_url: str, vcr_: Any
):
    """Test successful processing of vectorizer tasks"""
    _, conn = cli_db
    vectorizer_id = configure_same_table_vectorizer(cli_db[1], 3)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT embedding FROM blog where id='1' and id2='1';")
        result = cur.fetchone()
        assert result is not None
        assert result["embedding"] is None

    cassette = "same-table-vectorizer-3-rows.yaml"
    with vcr_.use_cassette(cassette):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)
    if result.exception:
        print(f"result: {result.stdout}")
        raise result.exception
    assert not result.exception
    assert result.exit_code == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT embedding FROM blog where id='1' and id2='1';")
        result = cur.fetchone()
        assert result is not None
        assert result["embedding"] is not None
        cur.execute("SELECT embedding FROM blog where id='2' and id2='2';")
        result = cur.fetchone()
        assert result is not None
        assert result["embedding"] is not None
        cur.execute("SELECT embedding FROM blog where id='3' and id2='3';")
        result = cur.fetchone()
        assert result is not None
        assert result["embedding"] is not None


def test_multiple_vectorizers(
    cli_db: tuple[TestDatabase, Connection], cli_db_url: str, vcr_: Any
):
    """Test successful processing of vectorizer tasks"""
    _, conn = cli_db
    table_name = setup_source_table(cli_db[1], 1)
    vectorizer_1 = configure_vectorizer(
        table_name, cli_db[1], skip_chunking=True, embedding_column="embedding"
    )
    vectorizer_2 = configure_vectorizer(
        table_name, cli_db[1], skip_chunking=True, embedding_column="embedding2"
    )

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT embedding, embedding2 FROM blog where id='1' and id2='1';")
        result = cur.fetchone()
        assert result is not None
        assert result["embedding"] is None
        assert result["embedding2"] is None

    cassette = "same-table-multi-vectorizer.yaml"
    with vcr_.use_cassette(cassette):
        result = run_vectorizer_worker(
            cli_db_url,
            extra_params=[
                "--vectorizer-id",
                str(vectorizer_1),
                "--vectorizer-id",
                str(vectorizer_2),
            ],
        )
    if result.exception:
        print(f"result: {result.stdout}")
        raise result.exception
    assert not result.exception
    assert result.exit_code == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT embedding, embedding2 FROM blog where id='1';")
        result = cur.fetchone()
        assert result is not None
        assert result["embedding"] is not None
        assert result["embedding2"] is not None
