from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import dict_row

from tests.vectorizer.cli.conftest import (
    TestDatabase,
    run_vectorizer_worker,
    setup_source_table,
)


@pytest.mark.postgres_params(ai_extension_version="0.8.0")
def test_080_vectorizer_definition(
    cli_db: tuple[TestDatabase, Connection], cli_db_url: str, vcr_: Any
):
    conn = cli_db[1]
    setup_source_table(conn, 3)

    with vcr_.use_cassette("test_old_target_table_schema_destination.yaml"):
        with conn.cursor(row_factory=dict_row) as cur:
            # Create vectorizer
            cur.execute("""
                    SELECT ai.create_vectorizer(
                    'blog'::regclass,
                    embedding => ai.embedding_openai('text-embedding-ada-002', 1536),
                    chunking => ai.chunking_character_text_splitter('content'),
                    formatting => ai.formatting_python_template('$chunk')
                    );
            """)  # type: ignore
            vectorizer_id = int(cur.fetchone()["create_vectorizer"])  # type: ignore
        run_vectorizer_worker(cli_db_url, vectorizer_id)

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM blog_embedding_store;")

            assert len(cur.fetchall()) == 3

        with conn.cursor() as cur:
            cur.execute("ALTER EXTENSION ai UPDATE;")
            cur.execute("INSERT INTO blog (id, id2, content) VALUES (20,20,'test');")
        run_vectorizer_worker(cli_db_url, vectorizer_id)

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM blog_embedding_store;")
            assert len(cur.fetchall()) == 4


@pytest.mark.postgres_params(ai_extension_version="0.8.0")
def test_errors_table_compatibility(
    cli_db: tuple[TestDatabase, Connection], cli_db_url: str, vcr_: Any
):
    conn = cli_db[1]
    setup_source_table(conn, 3)

    with vcr_.use_cassette("test_errors_table_compatibility.yaml"):
        # Create vectorizer with intentionally bad embedding model to produce an error
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ai.create_vectorizer(
                'blog'::regclass,
                embedding =>
                    ai.embedding_openai('intentionally-bad-embedding-model', 1536),
                chunking => ai.chunking_character_text_splitter('content'),
                formatting => ai.formatting_python_template('$chunk')
                );
            """)  # type: ignore
            vectorizer_id = int(cur.fetchone()[0])  # type: ignore
        run_vectorizer_worker(cli_db_url, vectorizer_id)

        with conn.cursor() as cur:
            cur.execute("SELECT * FROM ai.vectorizer_errors;")
            assert len(cur.fetchall()) > 0
