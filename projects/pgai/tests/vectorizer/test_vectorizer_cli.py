import json
import logging
import os
import re
import subprocess
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any

import openai
import psycopg
import pytest
from psycopg import Connection, sql
from psycopg.rows import dict_row
from testcontainers.ollama import OllamaContainer  # type: ignore
from testcontainers.postgres import PostgresContainer  # type: ignore

from tests.vectorizer import expected
from tests.vectorizer.utils import run_vectorizer_worker

count = 10000


class TestDatabase:
    __test__ = False
    """"""

    container: PostgresContainer
    dbname: str

    def __init__(self, container: PostgresContainer):
        global count
        dbname = f"test_{count}"
        count += 1
        self.container = container
        self.dbname = dbname
        url = self._create_connection_url(dbname="template1")
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS ai CASCADE")
            conn.execute(
                sql.SQL("CREATE DATABASE {0}").format(sql.Identifier(self.dbname))
            )

    def _create_connection_url(
        self,
        username: str | None = None,
        password: str | None = None,
        dbname: str | None = None,
    ):
        host = self.container._docker.host()  # type: ignore
        return super(PostgresContainer, self.container)._create_connection_url(  # type: ignore
            dialect="postgresql",
            username=username or self.container.username,
            password=password or self.container.password,
            dbname=dbname or self.dbname,
            host=host,
            port=self.container.port,
        )

    def get_connection_url(self) -> str:
        return self._create_connection_url()


@pytest.fixture
def cli_db(
    postgres_container: PostgresContainer,
) -> Generator[tuple[TestDatabase, Connection], None, None]:
    """Creates a test database with pgai installed"""

    test_database = TestDatabase(container=postgres_container)

    # Connect
    with psycopg.connect(
        test_database.get_connection_url(),
        autocommit=True,
    ) as conn:
        yield test_database, conn


@pytest.fixture
def cli_db_url(cli_db: tuple[TestDatabase, Connection]) -> str:
    """Constructs database URL from the cli_db fixture"""
    container, _ = cli_db
    return container.get_connection_url()


def test_worker_no_tasks(cli_db_url: str):
    """Test that worker handles no tasks gracefully"""
    result = run_vectorizer_worker(cli_db_url)

    # It exits successfully
    assert result.exit_code == 0
    assert "no vectorizers found" in result.output.lower()


def setup_source_table(
    connection: Connection,
    number_of_rows: int,
):
    table_name = "blog"
    with connection.cursor(row_factory=dict_row) as cur:
        # Create source table
        cur.execute(f"""
                CREATE TABLE {table_name} (
                    id INT NOT NULL PRIMARY KEY,
                    id2 INT NOT NULL,
                    content TEXT NOT NULL
                )
            """)
        # Insert test data
        values = [(i, i, f"post_{i}") for i in range(1, number_of_rows + 1)]
        cur.executemany(
            "INSERT INTO blog (id, id2, content) VALUES (%s, %s, %s)", values
        )
    return table_name


@pytest.fixture(scope="session")
def ollama_url():
    # If the OLLAMA_HOST environment variable is set, we assume that the user
    # has an Ollama container running and we don't need to start a new one.
    if "OLLAMA_HOST" in os.environ:
        yield os.environ["OLLAMA_HOST"]
    else:
        with OllamaContainer(
            image="ollama/ollama:latest",
            # Passing the ollama_home lets us reuse models that have already
            # been pulled to the `~/.ollama` path on the host machine.
            ollama_home=Path.home() / ".ollama",
        ) as ollama:
            yield ollama.get_endpoint()


def configure_vectorizer(
    source_table: str,
    connection: Connection,
    concurrency: int = 1,
    batch_size: int = 1,
    chunking: str = "chunking_character_text_splitter('content')",
    formatting: str = "formatting_python_template('$chunk')",
    embedding: str = "embedding_openai('text-embedding-ada-002', 1536)",
):
    with connection.cursor(row_factory=dict_row) as cur:
        # Create vectorizer
        cur.execute(f"""
            SELECT ai.create_vectorizer(
                '{source_table}'::regclass,
                embedding => ai.{embedding},
                chunking => ai.{chunking},
                formatting => ai.{formatting},
                processing => ai.processing_default(batch_size => {batch_size},
                                                    concurrency => {concurrency})
            )
        """)  # type: ignore
        vectorizer_id: int = int(cur.fetchone()["create_vectorizer"])  # type: ignore

        return vectorizer_id


def configure_openai_vectorizer(
    connection: Connection,
    openai_proxy_url: str | None = None,
    number_of_rows: int = 1,
    concurrency: int = 1,
    batch_size: int = 1,
    chunking: str = "chunking_character_text_splitter('content')",
    formatting: str = "formatting_python_template('$chunk')",
) -> int:
    """Creates and configures a vectorizer for testing"""
    table_name = setup_source_table(connection, number_of_rows)
    base_url = (
        f", base_url => '{openai_proxy_url}'" if openai_proxy_url is not None else ""
    )

    embedding = f"embedding_openai('text-embedding-ada-002', 1536{base_url})"
    return configure_vectorizer(
        table_name,
        connection,
        concurrency=concurrency,
        batch_size=batch_size,
        chunking=chunking,
        formatting=formatting,
        embedding=embedding,
    )


def configure_ollama_vectorizer(
    connection: Connection,
    ollama_url: str,
    number_of_rows: int = 1,
    concurrency: int = 1,
    batch_size: int = 1,
    chunking: str = "chunking_character_text_splitter('content')",
    formatting: str = "formatting_python_template('$chunk')",
) -> int:
    """Creates and configures an ollama vectorizer for testing"""

    table_name = setup_source_table(connection, number_of_rows)
    return configure_vectorizer(
        table_name,
        connection,
        concurrency=concurrency,
        batch_size=batch_size,
        chunking=chunking,
        formatting=formatting,
        embedding=f"embedding_ollama('nomic-embed-text',"
        f"768, base_url => '{ollama_url}')",
    )


def configure_voyageai_vectorizer_id(
    connection: Connection,
    number_of_rows: int = 1,
    concurrency: int = 1,
    batch_size: int = 1,
    chunking: str = "chunking_character_text_splitter('content')",
    formatting: str = "formatting_python_template('$chunk')",
) -> int:
    """Creates and configures a VoyageAI vectorizer for testing"""

    table_name = setup_source_table(connection, number_of_rows)
    return configure_vectorizer(
        table_name,
        connection,
        concurrency=concurrency,
        batch_size=batch_size,
        chunking=chunking,
        formatting=formatting,
        embedding="embedding_voyageai('voyage-3-lite', 512)",
    )


class TestWithOpenAiVectorizer:
    @pytest.mark.parametrize(
        "num_items,concurrency,batch_size,openai_proxy_url",
        [
            (1, 1, 1, None),
            (1, 1, 1, "8000"),
            (4, 2, 2, None),
        ],
        indirect=["openai_proxy_url"],
    )
    def test_process_vectorizer(
        self,
        cli_db: tuple[TestDatabase, Connection],
        cli_db_url: str,
        vcr_: Any,
        num_items: int,
        concurrency: int,
        batch_size: int,
        openai_proxy_url: str | None,
    ):
        """Test successful processing of vectorizer tasks"""
        _, conn = cli_db
        vectorizer_id = configure_openai_vectorizer(
            cli_db[1],
            openai_proxy_url,
            number_of_rows=num_items,
            concurrency=concurrency,
            batch_size=batch_size,
        )
        # Insert pre-existing embedding for first item
        with conn.cursor() as cur:
            cur.execute("""
               INSERT INTO
               blog_embedding_store(embedding_uuid, id, chunk_seq, chunk, embedding)
               VALUES (gen_random_uuid(), 1, 1, 'post_1',
                array_fill(0, ARRAY[1536])::vector)
            """)

        # Ensuring no OPENAI_API_KEY env set for the worker
        # to test loading secret from db
        del os.environ["OPENAI_API_KEY"]

        # When running the worker with cassette matching original test params
        cassette = (
            f"openai-character_text_splitter-chunk_value-"
            f"items={num_items}-batch_size={batch_size}-"
            f"custom_base_url={openai_proxy_url is not None}.yaml"
        )
        logging.getLogger("vcr").setLevel(logging.DEBUG)

        with vcr_.use_cassette(cassette):
            result = run_vectorizer_worker(cli_db_url, vectorizer_id, concurrency)

        assert not result.exception
        assert result.exit_code == 0

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT count(*) as count FROM blog_embedding_store;")
            assert cur.fetchone()["count"] == num_items  # type: ignore

    @pytest.mark.postgres_params(load_openai_key=False)
    def test_vectorizer_without_secrets_fails(
        self,
        cli_db: tuple[TestDatabase, Connection],
        cli_db_url: str,
        vcr_: Any,
    ):
        _, conn = cli_db
        vectorizer_id = configure_openai_vectorizer(cli_db[1])
        # Insert pre-existing embedding for first item
        with conn.cursor() as cur:
            cur.execute("""
               INSERT INTO
               blog_embedding_store(embedding_uuid, id, chunk_seq, chunk, embedding)
               VALUES (gen_random_uuid(), 1, 1, 'post_1',
                array_fill(0, ARRAY[1536])::vector)
                    """)
        # Ensuring no OPENAI_API_KEY env set for the worker
        del os.environ["OPENAI_API_KEY"]

        cassette = (
            "openai-character_text_splitter-chunk_value-" "items=1-batch_size=1.yaml"
        )
        logging.getLogger("vcr").setLevel(logging.DEBUG)
        with vcr_.use_cassette(cassette):
            result = run_vectorizer_worker(cli_db_url, vectorizer_id)

        assert result.exit_code == 1
        assert "ApiKeyNotFoundError" in result.output

    def test_document_exceeds_model_context_length(
        self,
        cli_db: tuple[TestDatabase, Connection],
        cli_db_url: str,
        vcr_: Any,
    ):
        """Test handling of documents that exceed the model's token limit"""
        _, conn = cli_db
        # Given a vectorizer configuration
        vectorizer_id = configure_openai_vectorizer(
            cli_db[1],
            number_of_rows=2,
            batch_size=2,
            chunking="chunking_recursive_character_text_splitter('content', 128, 10,"
            " separators => array[E'\n\n'])",
        )
        with conn.cursor(row_factory=dict_row) as cur:
            long_content = "AGI" * 5000
            cur.execute(
                f"UPDATE blog SET CONTENT = '{long_content}' where id = '2'",
            )

        # When running the worker
        with vcr_.use_cassette("test_document_in_batch_too_long.yaml"):
            result = run_vectorizer_worker(cli_db_url, vectorizer_id)

        assert result.exit_code == 0

        # Then only the normal document should be embedded
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM blog_embedding_store ORDER BY id")
            records = cur.fetchall()
            assert len(records) == 1
            record = records[0]

            # Verify the embedded document
            assert record["id"] == 1
            assert record["chunk"] == "post_1"
            assert (
                record["embedding"]
                == expected.embeddings["openai-character_text_splitter-chunk_value-1-1"]
            )

            # Check error was logged
            cur.execute("SELECT * FROM ai.vectorizer_errors")
            errors = cur.fetchall()
            assert len(errors) == 1
            error = errors[0]
            assert error["message"] == "chunk exceeds model context length"
            assert error["details"]["pk"]["id"] == 2
            assert (
                error["details"]["error_reason"]
                == "chunk exceeds the text-embedding-ada-002"
                " model context length of 8192 tokens"
            )

    def test_invalid_api_key_error(
        self,
        cli_db: tuple[TestDatabase, Connection],
        cli_db_url: str,
        vcr_: Any,
    ):
        """Test that worker handles invalid API key appropriately"""
        _, conn = cli_db

        vectorizer_id = configure_openai_vectorizer(
            cli_db[1],
            number_of_rows=2,
            batch_size=2,
            chunking="chunking_recursive_character_text_splitter('content')",
        )

        os.environ["OPENAI_API_KEY"] = "invalid"

        # When running the worker and getting an invalid api key response
        with vcr_.use_cassette("test_invalid_api_key_error.yaml"):
            try:
                run_vectorizer_worker(cli_db_url, vectorizer_id)
            except openai.AuthenticationError as e:
                assert e.code == 401

        # Ensure there's an entry in the errors table
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM ai.vectorizer_errors")
            records = cur.fetchall()
            assert len(records) == 1
            error = records[0]
            assert error["id"] == vectorizer_id
            assert error["message"] == "embedding provider failed"
            assert error["details"] == {
                "provider": "openai",
                "error_reason": "Error code: 401 - {'error': {'message': "
                "'Incorrect API key provided: invalid."
                " You can find your API key at"
                " https://platform.openai.com/account/api-keys.',"
                " 'type': 'invalid_request_error', 'param': None,"
                " 'code': 'invalid_api_key'}}",
            }

    def test_invalid_function_arguments(
        self, cli_db: tuple[TestDatabase, Connection], cli_db_url: str
    ):
        """Test that worker handles invalid embedding model arguments appropriately"""
        _, conn = cli_db

        vectorizer_id = configure_openai_vectorizer(cli_db[1])
        # And a vectorizer with invalid embedding dimensions
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ai.vectorizer
                SET config = jsonb_set(
                    config,
                    '{embedding,dimensions}',
                    '128'::jsonb
                )
                WHERE id = %s
            """,
                (vectorizer_id,),
            )

        # When running the worker
        try:
            run_vectorizer_worker(cli_db_url, vectorizer_id)
        except ValueError as e:
            assert str(e) == "dimensions must be 1536 for text-embedding-ada-002"

        # Then an error was logged
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM ai.vectorizer_errors")
            records = cur.fetchall()
            assert len(records) == 1
            error = records[0]
            assert error["id"] == vectorizer_id
            assert error["message"] == "embedding provider failed"
            assert error["details"] == {
                "provider": "openai",
                "error_reason": "dimensions must be 1536 for text-embedding-ada-002",
            }


@pytest.mark.parametrize(
    "num_items,concurrency,batch_size",
    [
        (1, 1, 1),
        (4, 2, 2),
    ],
)
def test_ollama_vectorizer(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    ollama_url: str,
    num_items: int,
    concurrency: int,
    batch_size: int,
):
    """Test successful processing of vectorizer tasks"""
    _, conn = cli_db

    vectorizer_id = configure_ollama_vectorizer(
        cli_db[1],
        ollama_url,
        number_of_rows=num_items,
        concurrency=concurrency,
        batch_size=batch_size,
    )
    # Insert pre-existing embedding for first item
    with conn.cursor() as cur:
        cur.execute("""
           INSERT INTO
           blog_embedding_store(embedding_uuid, id, chunk_seq, chunk, embedding)
           VALUES (gen_random_uuid(), 1, 1, 'post_1',
            array_fill(0, ARRAY[768])::vector)
        """)
    result = run_vectorizer_worker(cli_db_url, vectorizer_id, concurrency)

    assert not result.exception
    assert result.exit_code == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as count FROM blog_embedding_store;")
        assert cur.fetchone()["count"] == num_items  # type: ignore


@pytest.mark.parametrize(
    "num_items,concurrency,batch_size",
    [
        (1, 1, 1),
        (4, 2, 2),
    ],
)
def test_voyageai_vectorizer(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
    num_items: int,
    concurrency: int,
    batch_size: int,
):
    """Test successful processing of vectorizer tasks"""
    if "VOYAGE_API_KEY" not in os.environ:
        os.environ["VOYAGE_API_KEY"] = "A FAKE KEY"
    _, conn = cli_db
    vectorizer_id = configure_voyageai_vectorizer_id(
        cli_db[1],
        number_of_rows=num_items,
        concurrency=concurrency,
        batch_size=batch_size,
    )
    # Insert pre-existing embedding for first item
    with conn.cursor() as cur:
        cur.execute("""
           INSERT INTO
           blog_embedding_store(embedding_uuid, id, chunk_seq, chunk, embedding)
           VALUES (gen_random_uuid(), 1, 1, 'post_1',
            array_fill(0, ARRAY[512])::vector)
        """)

    # When running the worker with cassette matching original test params
    cassette = (
        f"voyageai-character_text_splitter-chunk_value-"
        f"items={num_items}-batch_size={batch_size}.yaml"
    )
    logging.getLogger("vcr").setLevel(logging.DEBUG)
    with vcr_.use_cassette(cassette):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id, concurrency)

    assert not result.exception
    assert result.exit_code == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as count FROM blog_embedding_store;")
        assert cur.fetchone()["count"] == num_items  # type: ignore


def test_voyageai_vectorizer_fails_when_api_key_is_not_set(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
):
    """Test missing API Key"""
    _, conn = cli_db

    # Ensure API key env var is not set.
    if "VOYAGE_API_KEY" in os.environ:
        del os.environ["VOYAGE_API_KEY"]

    # Set up vectorizer which will fail to embed chunk
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("CREATE TABLE blog(id bigint primary key, content text);")
        cur.execute("""SELECT ai.create_vectorizer(
                'blog',
                embedding => ai.embedding_voyageai(
                    'voyage-3-lite',
                    512
                ),
                chunking => ai.chunking_character_text_splitter('content')
        )""")  # noqa
        cur.execute("INSERT INTO blog (id, content) VALUES(1, repeat('1', 100000))")

    result = run_vectorizer_worker(cli_db_url)

    assert result.exit_code == 1
    assert "ApiKeyNotFoundError" in result.output


class TestExitOnError:
    def test_vectorizer_exits_with_error_when_no_ai_extension(
        self,
        postgres_container: PostgresContainer,
    ):
        result = run_vectorizer_worker(postgres_container.get_connection_url())

        assert result.exit_code == 1
        assert "the pgai extension is not installed" in result.output.lower()

    def test_vectorizer_exits_with_error_when_vectorizers_specified_but_missing(
        self, cli_db_url: str
    ):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id=0)
        assert result.exit_code != 0
        assert "invalid vectorizers, wanted: [0], got: []" in result.output


class TestNoExitOnError:
    def test_vectorizer_does_not_exit_with_error_when_no_ai_extension(
        self,
        postgres_container: PostgresContainer,
    ):
        result = run_vectorizer_worker(
            postgres_container.get_connection_url(),
            extra_params=["--exit-on-error=false"],
        )

        assert result.exit_code == 0
        assert "the pgai extension is not installed" in result.output.lower()

    def test_vectorizer_does_not_exit_with_error_when_vectorizers_specified_but_missing(
        self, cli_db_url: str
    ):
        result = run_vectorizer_worker(
            cli_db_url, vectorizer_id=0, extra_params=["--exit-on-error=false"]
        )
        assert result.exit_code == 0
        assert "invalid vectorizers, wanted: [0], got: []" in result.output


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
            embedding => ai.embedding_openai('text-embedding-3-small', 768),
            chunking => ai.chunking_recursive_character_text_splitter('contents')
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
    _, conn = cli_db
    vectorizer_id = configure_openai_vectorizer(
        cli_db[1],
        number_of_rows=2,
        batch_size=2,
        chunking="chunking_recursive_character_text_splitter('content', 100, 20,"
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
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("UPDATE blog SET content = %s WHERE id = 1", (sample_content,))
        cur.execute("UPDATE blog SET content = %s WHERE id = 2", (shorter_content,))

    # When running the worker
    with vcr_.use_cassette("test_recursive_character_splitting.yaml"):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert result.exit_code == 0

    # Then verify the chunks were created correctly
    with conn.cursor(row_factory=dict_row) as cur:
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


@pytest.mark.parametrize(
    "chunking",
    [
        "chunking_character_text_splitter('content')",
        "chunking_recursive_character_text_splitter('content')",
    ],
)
def test_vectorization_successful_with_null_contents(
    cli_db: tuple[PostgresContainer, Connection],
    cli_db_url: str,
    ollama_url: str,
    chunking: str,
):
    _, conn = cli_db
    vectorizer_id = configure_ollama_vectorizer(conn, ollama_url, chunking=chunking)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("ALTER TABLE blog ALTER COLUMN content DROP NOT NULL;")
        cur.execute("UPDATE blog SET content = null;")

    result = run_vectorizer_worker(cli_db_url, vectorizer_id)

    assert not result.exception
    assert result.exit_code == 0

    _, conn = cli_db

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as count FROM blog_embedding_store;")
        assert cur.fetchone()["count"] == 0  # type: ignore


@pytest.mark.parametrize(
    "num_items, concurrency, batch_size",
    [
        (1, 1, 1),
        (4, 2, 2),
    ],
)
@pytest.mark.parametrize(
    "embedding",
    [
        ("openai/text-embedding-3-small", 1536, {}, "OPENAI_API_KEY"),
        ("voyage/voyage-3-lite", 512, {}, "VOYAGE_API_KEY"),
        ("mistral/mistral-embed", 1024, {}, "MISTRAL_API_KEY"),
        ("cohere/embed-english-v3.0", 1024, {}, "COHERE_API_KEY"),
        (
            "huggingface/microsoft/codebert-base",
            768,
            {"wait_for_model": True, "use_cache": False},
            "HUGGINGFACE_API_KEY",
        ),
        (
            "azure/text-embedding-3-small",
            1536,
            {
                "api_base": os.getenv("AZURE_OPENAI_API_BASE"),
                "api_version": os.getenv("AZURE_OPENAI_API_VERSION"),
            },
            "AZURE_OPENAI_API_KEY",
        ),
    ],
)
def test_litellm_vectorizer(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    embedding: tuple[str, int, dict[str, Any], str],
    num_items: int,
    concurrency: int,
    batch_size: int,
    vcr_: Any,
):
    model, dimensions, extra_options, api_key_name = embedding
    function = "embedding_litellm"

    if model == "huggingface/microsoft/codebert-base":
        pytest.skip("unable to get huggingface tests to reproduce reliably")

    if api_key_name not in os.environ:
        pytest.skip(f"environment variable '{api_key_name}' unset")

    embedding_str = f"{function}('{model}', {dimensions}, extra_options => '{json.dumps(extra_options)}'::jsonb)"  # noqa: E501 Line too long

    source_table = setup_source_table(cli_db[1], num_items)
    vectorizer_id = configure_vectorizer(
        source_table,
        connection=cli_db[1],
        concurrency=concurrency,
        batch_size=batch_size,
        embedding=embedding_str,
    )

    _, conn = cli_db
    # Insert pre-existing embedding for first item
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("""
           INSERT INTO
           blog_embedding_store(embedding_uuid, id, chunk_seq, chunk, embedding)
           VALUES (gen_random_uuid(), 1, 1, 'post_1',
            array_fill(0, ARRAY[{0}])::vector)
        """).format(dimensions)
        )

    stripped_model = re.sub(r"\W", "_", model)

    # When running the worker with cassette matching original test params
    cassette = f"{function}_{stripped_model}_{dimensions}_items_{num_items}_batch_size_{batch_size}.yaml"  # noqa: E501 Line too long
    logging.getLogger("vcr").setLevel(logging.DEBUG)
    with vcr_.use_cassette(cassette):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id, concurrency)

    assert not result.exception
    assert result.exit_code == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as count FROM blog_embedding_store;")
        assert cur.fetchone()["count"] == num_items  # type: ignore
