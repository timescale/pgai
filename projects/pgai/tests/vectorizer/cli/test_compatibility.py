from typing import Any

import psycopg
from psycopg.rows import dict_row
from testcontainers.postgres import PostgresContainer

from tests.vectorizer.cli.conftest import (
    run_vectorizer_worker,
    setup_source_table,
)


def test_old_target_table_schema_destination(postgres_container: PostgresContainer, vcr_: Any):
    url = super(PostgresContainer, postgres_container)._create_connection_url(  # type: ignore
        dialect="postgresql",
        username=postgres_container.username,
        password=postgres_container.password,
        dbname="template1",
        host=postgres_container._docker.host(),  # type: ignore
        port=postgres_container.port,
    )
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS ai WITH VERSION '0.8.0' CASCADE")
        conn.execute("CREATE DATABASE test_vectorizer_080")
    
    url = super(PostgresContainer, postgres_container)._create_connection_url(  # type: ignore
        dialect="postgresql",
        username=postgres_container.username,
        password=postgres_container.password,
        dbname="test_vectorizer_080",
        host=postgres_container._docker.host(),  # type: ignore
        port=postgres_container.port,
    )
    with psycopg.connect(url, autocommit=True) as conn:
        setup_source_table(conn, 10)
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
        with vcr_.use_cassette("test_old_target_table_schema_destination"):
            run_vectorizer_worker(url, vectorizer_id)
    
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM blog_embedding_store;")
            assert cur.fetchone() is not None
