from collections.abc import Generator

import psycopg
import pytest
from click.testing import CliRunner, Result
from psycopg import Connection, sql
from psycopg.rows import dict_row
from testcontainers.postgres import PostgresContainer  # type: ignore

from pgai.cli import vectorizer_worker

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


def run_vectorizer_worker(
    db_url: str,
    vectorizer_id: int | None = None,
    concurrency: int = 1,
    extra_params: list[str] | None = None,
) -> Result:
    args = [
        "--db-url",
        db_url,
        "--once",
        "--concurrency",
        str(concurrency),
    ]
    if vectorizer_id is not None:
        args.extend(["--vectorizer-id", str(vectorizer_id)])
    if extra_params:
        args.extend(extra_params)

    return CliRunner().invoke(
        vectorizer_worker,
        args,
        catch_exceptions=False,
    )
