from collections.abc import Generator, Mapping
from typing import Any

import psycopg
import pytest
from click.testing import CliRunner, Result
from psycopg import Connection, sql
from psycopg.rows import dict_row
from testcontainers.postgres import PostgresContainer  # type: ignore

from pgai.cli import download_models as download_models_cmd
from pgai.cli import vectorizer_worker

count = 10000


class TestDatabase:
    __test__ = False
    """"""

    container: PostgresContainer
    dbname: str

    def __init__(self, container: PostgresContainer, extension_version: str = ""):
        global count
        dbname = f"test_{count}"
        count += 1
        self.container = container
        self.dbname = dbname
        url = self._create_connection_url(dbname="postgres")
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(
                sql.SQL("CREATE DATABASE {0}").format(sql.Identifier(self.dbname))
            )

        url = self._create_connection_url(dbname=self.dbname)
        with psycopg.connect(url, autocommit=True) as conn:
            if extension_version != "":
                conn.execute(
                    f"CREATE EXTENSION IF NOT EXISTS ai"  # type: ignore
                    f"   WITH VERSION '{extension_version}' CASCADE"
                )
            else:
                import pgai

                pgai.install(url)

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
    request: pytest.FixtureRequest,
) -> Generator[tuple[TestDatabase, Connection], None, None]:
    """Creates a test database with pgai installed"""
    marker: pytest.Mark | None = None
    for marker in request.node.iter_markers():  # type: ignore
        if marker.name == "postgres_params":  # type: ignore
            break
    params: Mapping[str, Any] = marker.kwargs if marker else {}  # type: ignore
    ai_extension_version: str = params.get("ai_extension_version", "")  # type: ignore
    test_database = TestDatabase(
        container=postgres_container,
        extension_version=ai_extension_version,  # type: ignore
    )

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
    chunking: str = "chunking_character_text_splitter()",
    formatting: str = "formatting_python_template('$chunk')",
    embedding: str = "embedding_openai('text-embedding-ada-002', 1536)",
    loading: str | None = "ai.loading_column(column_name => 'content')",
    parsing: str | None = None,
):
    with connection.cursor(row_factory=dict_row) as cur:
        # Create vectorizer
        parsing = f", parsing => {parsing}" if parsing else ""
        cur.execute(f"""
            SELECT ai.create_vectorizer(
                '{source_table}'::regclass,
                loading => {loading},
                embedding => ai.{embedding},
                chunking => ai.{chunking},
                formatting => ai.{formatting},
                processing => ai.processing_default(batch_size => {batch_size},
                                                    concurrency => {concurrency})
                {parsing}
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
        "--log-level",
        "debug",
    ]
    if vectorizer_id is not None:
        args.extend(["--vectorizer-id", str(vectorizer_id)])
    if extra_params:
        args.extend(extra_params)

    result = CliRunner().invoke(
        vectorizer_worker,
        args,
        catch_exceptions=False,
    )
    if result.exit_code != 0:
        print(result.output)
    return result


def download_docling_models():
    CliRunner().invoke(download_models_cmd)
