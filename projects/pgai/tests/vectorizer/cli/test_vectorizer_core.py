import asyncio
import os
import subprocess
import time
from typing import Any

import pytest
from psycopg import Connection
from psycopg.rows import dict_row
from testcontainers.postgres import PostgresContainer  # type: ignore

from pgai.vectorizer import Executor, Vectorizer
from pgai.vectorizer.features.features import Features
from pgai.vectorizer.worker_tracking import WorkerTracking
from tests.vectorizer.cli.conftest import (
    TestDatabase,
    configure_vectorizer,
    run_vectorizer_worker,
    setup_source_table,
)


def test_worker_no_tasks(cli_db_url: str):
    """Test that worker handles no tasks gracefully"""
    result = run_vectorizer_worker(cli_db_url)

    # It exits successfully
    assert result.exit_code == 0
    assert "no vectorizers found" in result.output.lower()


def test_vectorizer_exits_with_error_when_no_ai_extension(
    postgres_container: PostgresContainer,
):
    result = run_vectorizer_worker(postgres_container.get_connection_url())

    assert result.exit_code == 1
    assert "pgai is not installed in the database" in result.output.lower()


def test_vectorizer_exits_with_error_when_vectorizers_specified_but_missing(
    cli_db_url: str,
):
    result = run_vectorizer_worker(cli_db_url, vectorizer_id=0)
    assert result.exit_code != 0
    assert "invalid vectorizers, wanted: [0], got: []" in result.output


def test_vectorizer_does_not_exit_with_error_when_no_ai_extension(
    postgres_container: PostgresContainer,
):
    result = run_vectorizer_worker(
        postgres_container.get_connection_url(),
        extra_params=["--exit-on-error=false"],
    )

    assert result.exit_code == 0
    assert "pgai is not installed in the database" in result.output.lower()


def test_vectorizer_does_not_exit_with_error_when_vectorizers_specified_but_missing(
    cli_db_url: str,
):
    result = run_vectorizer_worker(
        cli_db_url, vectorizer_id=0, extra_params=["--exit-on-error=false"]
    )
    assert result.exit_code == 0
    assert "invalid vectorizers, wanted: [0], got: []" in result.output


# It's taking longer than expected to generate the output on CI
# causing the test to fail repeatedly
@pytest.mark.skipif(os.getenv("CI") is not None, reason="flaky in CI")
def test_vectorizer_picks_up_new_vectorizer(
    cli_db: tuple[TestDatabase, Connection],
):
    postgres_container, con = cli_db
    db_url = postgres_container.get_connection_url()
    test_env = os.environ.copy()
    test_env["OPENAI_API_KEY"] = (
        "empty"  # the key must be set, but doesn't need to be valid
    )
    process = subprocess.Popen(
        [
            "python",
            "-m",
            "pgai",
            "vectorizer",
            "worker",
            "--db-url",
            db_url,
            "--poll-interval",
            "0.1s",
        ],
        env=test_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    # the typings for subprocess.Popen are bad, see https://github.com/python/typeshed/issues/3831
    assert process.stdout is not None

    os.set_blocking(
        process.stdout.fileno(), False
    )  # allow capturing all output without blocking
    count = 0
    while True:
        output = "\n".join(process.stdout.readlines())
        if output != "":
            assert "no vectorizers found" in output
            assert "running vectorizer" not in output
            break
        else:
            # assume that we'll see the output we want to see within 10s
            assert count < 20
            count += 1
            time.sleep(0.5)

    with con.cursor() as cur:
        cur.execute("CREATE TABLE test(id bigint primary key, contents text)")
        cur.execute("""SELECT ai.create_vectorizer('test'::regclass,
            loading => ai.loading_column('contents'),
            embedding => ai.embedding_openai('text-embedding-3-small', 768),
            chunking => ai.chunking_recursive_character_text_splitter()
        );
        """)
    count = 0
    while True:
        output = "\n".join(process.stdout.readlines())
        if "running vectorizer" not in output:
            # assume that we see the output we want to within 10s
            assert count < 20
            count += 1
            time.sleep(0.5)
        else:
            break
    process.terminate()


def test_recursive_character_splitting(
    cli_db: tuple[PostgresContainer, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that recursive character splitting correctly chunks
    content based on natural boundaries"""
    _, connection = cli_db
    table_name = setup_source_table(connection, 2)
    vectorizer_id = configure_vectorizer(
        table_name,
        cli_db[1],
        batch_size=2,
        chunking="chunking_recursive_character_text_splitter(100, 20,"
        " separators => array[E'\\n\\n', E'\\n', ' '])",
    )

    # Given content with natural splitting points
    sample_content = """Introduction to Machine Learning

Machine learning is a subset of artificial intelligence that focuses on data and
algorithms.
It enables systems to learn and improve from experience.

Key Concepts:
1. Supervised Learning
2. Unsupervised Learning
3. Reinforcement Learning

Each type has its own unique applications and methodologies."""

    shorter_content = "This is a shorter post that shouldn't need splitting."

    # Update the test data with our structured content
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("UPDATE blog SET content = %s WHERE id = 1", (sample_content,))
        cur.execute("UPDATE blog SET content = %s WHERE id = 2", (shorter_content,))

    # When running the worker
    with vcr_.use_cassette("test_recursive_character_splitting.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 0

    # Then verify the chunks were created correctly
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT id, chunk_seq, chunk
            FROM blog_embedding_store
            ORDER BY id, chunk_seq
        """)
        chunks = cur.fetchall()

        # Verify we got multiple chunks for the longer content
        first_doc_chunks = [c for c in chunks if c["id"] == 1]
        assert (
            len(first_doc_chunks) > 1
        ), "Long document should be split into multiple chunks"

        # Verify chunk boundaries align with natural breaks
        assert any(
            "Introduction to Machine Learning" in c["chunk"] for c in first_doc_chunks
        ), "Should have a chunk starting with the title"

        assert not all(
            "Introduction to Machine Learning" in c["chunk"] for c in first_doc_chunks
        ), "Not all chunks should start with the title"

        assert any(
            "Key Concepts:" in c["chunk"] for c in first_doc_chunks
        ), "Should have a chunk containing the key concepts section"

        # Verify shorter content remains as single chunk
        second_doc_chunks = [c for c in chunks if c["id"] == 2]
        assert len(second_doc_chunks) == 1, "Short document should be a single chunk"
        assert second_doc_chunks[0]["chunk"] == shorter_content

        # Verify chunk sequences are correct
        for doc_chunks in [first_doc_chunks, second_doc_chunks]:
            sequences = [c["chunk_seq"] for c in doc_chunks]
            assert sequences == list(
                range(len(sequences))
            ), "Chunk sequences should be sequential starting from 0"


def test_regression_source_table_has_locked_column(
    cli_db: tuple[PostgresContainer, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that worker succeeds on source table with column named 'locked'"""
    _, connection = cli_db
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "CREATE TABLE test_locked (id bigint primary key, content text, locked bool)"  # noqa
        )
        cur.execute(
            "INSERT INTO test_locked (id, content, locked) VALUES (1, 'hello world', false)"  # noqa
        )

    vectorizer_id = configure_vectorizer(
        "test_locked",
        cli_db[1],
    )

    # When running the worker
    with vcr_.use_cassette("test_regression_source_table_has_locked_column.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 0

    # Then verify the chunks were created correctly
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) FROM test_locked_embedding_store")
        results = cur.fetchall()
        assert results[0]["count"] == 1


def test_disabled_vectorizer_is_skipped(
    cli_db: tuple[PostgresContainer, Connection],
    cli_db_url: str,
):
    """Test that disabled vectorizers won't process any batches"""
    _, connection = cli_db
    table_name = setup_source_table(connection, 2)
    # Given a disabled vectorizer.
    vectorizer_id = configure_vectorizer(
        table_name,
        cli_db[1],
        batch_size=2,
        chunking="chunking_recursive_character_text_splitter(100, 20,"
        " separators => array[E'\\n\\n', E'\\n', ' '])",
    )
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("select ai.disable_vectorizer_schedule(%s)", (vectorizer_id,))

    # When the worker is executed.
    result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 0, result.output

    with connection.cursor(row_factory=dict_row) as cur:
        # Then no chunks were created.
        cur.execute("""
            SELECT count(*)
            FROM blog_embedding_store
        """)
        row = cur.fetchone()
        assert row is not None and row["count"] == 0

        # And the pending items are still present.
        cur.execute(
            """
            SELECT pending_items, disabled
            FROM ai.vectorizer_status
            WHERE id = %s
        """,
            (vectorizer_id,),
        )
        row = cur.fetchone()
        assert row is not None and row["pending_items"] == 2
        assert row["disabled"]


def test_disabled_vectorizer_is_skipped_before_next_batch(
    cli_db: tuple[PostgresContainer, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that a disabled vectorizer will exit before starting a new batch"""
    _, connection = cli_db
    table_name = setup_source_table(connection, 2)

    # Given a vectorizer that has 2 items and a batch size of 1
    vectorizer_id = configure_vectorizer(
        table_name,
        cli_db[1],
        batch_size=1,
        chunking="chunking_recursive_character_text_splitter(100, 20,"
        " separators => array[E'\\n\\n', E'\\n', ' '])",
    )
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "select pg_catalog.to_jsonb(v) as vectorizer from ai.vectorizer v where v.id = %s",  # noqa
            (vectorizer_id,),
        )
        row = cur.fetchone()
    assert row is not None
    vectorizer = Vectorizer(**row["vectorizer"])
    vectorizer.config.embedding.set_api_key(  # type: ignore
        {"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")}
    )
    features = Features.for_testing_latest_version()
    worker_tracking = WorkerTracking(cli_db_url, 500, features, "0.0.1")

    # When the vectorizer is disabled after processing the first batch.
    def should_continue_processing_hook(_loops: int, _res: int) -> bool:
        with connection.cursor(row_factory=dict_row) as cur:
            cur.execute("select ai.disable_vectorizer_schedule(%s)", (vectorizer_id,))
        return True

    with vcr_.use_cassette(
        "test_disabled_vectorizer_is_skipped_before_next_batch.yaml"
    ):
        results = asyncio.run(
            Executor(
                cli_db_url,
                vectorizer,
                features,
                worker_tracking,
                should_continue_processing_hook,
            ).run()
        )
    # Then it successfully exits after the first batch.
    assert results == 1

    with connection.cursor(row_factory=dict_row) as cur:
        # And it embeds a single item.
        cur.execute("""
            SELECT count(*)
            FROM blog_embedding_store
        """)
        row = cur.fetchone()
        assert row is not None and row["count"] == 1

        # And there's a single pending item.
        cur.execute(
            """
            SELECT pending_items
            FROM ai.vectorizer_status
            WHERE id = %s
        """,
            (vectorizer_id,),
        )
        row = cur.fetchone()
        assert row is not None and row["pending_items"] == 1


def test_disabled_vectorizer_is_backwards_compatible(
    cli_db: tuple[PostgresContainer, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test the backwards compatible path. Even if the vectorizer is disabled
    it'll get embedded. It's not a 100% backwards compatible test, since the DB
    has support for disable_vectorizers, but it tests the path"""
    _, connection = cli_db
    table_name = setup_source_table(connection, 2)

    # Given a vectorizer and the `disable_vectorizers` feature is disabled.
    vectorizer_id = configure_vectorizer(
        table_name,
        cli_db[1],
        batch_size=2,
        chunking="chunking_recursive_character_text_splitter(100, 20,"
        " separators => array[E'\\n\\n', E'\\n', ' '])",
    )
    features = Features.for_testing_no_features()
    worker_tracking = WorkerTracking(cli_db_url, 500, features, "0.0.1")
    assert not features.disable_vectorizers

    # And the vectorizer is disabled so that we can test the backwards
    # compatible path, to the best of our ability.
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("select ai.disable_vectorizer_schedule(%s)", (vectorizer_id,))

    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "select pg_catalog.to_jsonb(v) as vectorizer from ai.vectorizer v where v.id = %s",  # noqa
            (vectorizer_id,),
        )
        row = cur.fetchone()
    assert row is not None
    vectorizer = Vectorizer(**row["vectorizer"])
    vectorizer.config.embedding.set_api_key(  # type: ignore
        {"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")}
    )

    # When the vectorizer is executed.
    with vcr_.use_cassette("test_disabled_vectorizer_is_backwards_compatible.yaml"):
        results = asyncio.run(
            Executor(cli_db_url, vectorizer, features, worker_tracking).run()
        )

    # Then the disable is ignored and the vectorizer successfully exits after
    # processing the batches.
    assert results == 2

    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT count(*)
            FROM blog_embedding_store
        """)
        row = cur.fetchone()
        assert row is not None and row["count"] == 2

        cur.execute(
            """
            SELECT pending_items
            FROM ai.vectorizer_status
            WHERE id = %s
        """,
            (vectorizer_id,),
        )
        row = cur.fetchone()
        assert row is not None and row["pending_items"] == 0


def test_chunking_none(
    cli_db: tuple[PostgresContainer, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that chunking_none preserves the document as a single chunk"""
    _, connection = cli_db
    table_name = setup_source_table(connection, 2)
    vectorizer_id = configure_vectorizer(
        table_name,
        cli_db[1],
        batch_size=2,
        chunking="chunking_none()",
    )

    # Given content with natural splitting points that would normally be chunked
    sample_content = """Introduction to Machine Learning

    Machine learning is a subset of artificial intelligence that focuses on data and
    algorithms.
    It enables systems to learn and improve from experience.

    Key Concepts:
    1. Supervised Learning
    2. Unsupervised Learning
    3. Reinforcement Learning

    Each type has its own unique applications and methodologies."""

    shorter_content = "This is a shorter post that shouldn't need splitting."

    # Update the test data with our structured content
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("UPDATE blog SET content = %s WHERE id = 1", (sample_content,))
        cur.execute("UPDATE blog SET content = %s WHERE id = 2", (shorter_content,))

    # When running the worker
    with vcr_.use_cassette("test_chunking_none.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 0

    # Then verify each document remains as a single chunk
    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT id, chunk_seq, chunk
            FROM blog_embedding_store
            ORDER BY id, chunk_seq
        """)
        chunks = cur.fetchall()

        # Verify each document has exactly one chunk
        first_doc_chunks = [c for c in chunks if c["id"] == 1]
        assert (
            len(first_doc_chunks) == 1
        ), "Long document should remain as a single chunk with chunking_none"
        assert first_doc_chunks[0]["chunk"] == sample_content

        # Verify short content is also a single chunk
        second_doc_chunks = [c for c in chunks if c["id"] == 2]
        assert len(second_doc_chunks) == 1, "Short document should be a single chunk"
        assert second_doc_chunks[0]["chunk"] == shorter_content

        # Verify chunk sequences are correct (should all be 0)
        for doc_chunks in [first_doc_chunks, second_doc_chunks]:
            assert (
                doc_chunks[0]["chunk_seq"] == 0
            ), "Chunk sequence should be 0 for single chunks"
