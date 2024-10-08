import os
from dataclasses import dataclass
from typing import Any

import psycopg
import pytest
import tiktoken
import vcr  # type:ignore
from psycopg import sql
from testcontainers.postgres import PostgresContainer  # type:ignore

DIMENSION_COUNT = 1536


@pytest.fixture(autouse=True)
def __env_setup(monkeypatch):  # type:ignore
    # Capture the current environment variables to restore after the test. The
    # lambda function sets an evironment variable for using the secrets. We
    # need to clear the environment after a test runs.
    original_env = os.environ.copy()

    # OpenAI uses tiktoken to get the model encoding specification to use when
    # tokenizing. The model spec is fetched with a GET request and stored in a
    # cache directory. We need to create a temp dir as cache, to trigger a
    # request on every test.
    monkeypatch.setenv("TIKTOKEN_CACHE_DIR", "")  # type:ignore
    yield

    tiktoken.registry.ENCODINGS = {}

    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(scope="session")
def vcr_():
    return vcr.VCR(
        serializer="yaml",
        cassette_library_dir="tests/vectorizer/cassettes",
        record_mode=vcr.mode.ONCE,
        filter_headers=["authorization"],
        match_on=["method", "scheme", "host", "port", "path", "query", "body"],
    )


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("timescale/timescaledb-ha:pg16", driver=None) as postgres:
        yield postgres


@pytest.fixture
def embedding_table_config():
    return {
        "source_schema": "public",
        "source_table": "blog",
        "source_pk": [
            {"attname": "id", "pknum": 1, "attnum": 1, "typname": "int4"},
            {"attname": "id2", "pknum": 2, "attnum": 2, "typname": "int4"},
        ],
        "embeddings_table": "blog_embedding",
        "queue_schema": "ai",
        "queue_table": "work_queue",
        "target_schema": "ai",
        "target_table": "embeddings",
    }


@pytest.fixture
def db(
    postgres_container: PostgresContainer, embedding_table_config: dict[str, Any]
) -> Any:
    role = "tsdbquerier"
    password = "my-password"
    db_host = postgres_container._docker.host()  # type: ignore
    with psycopg.connect(
        postgres_container.get_connection_url(host=db_host),
        autocommit=True,
    ) as conn:
        conn.execute(
            sql.SQL("DROP USER IF EXISTS {}").format(
                sql.Identifier(role),
            )
        )
        conn.execute(
            sql.SQL("CREATE USER {} WITH SUPERUSER PASSWORD {}").format(
                sql.Identifier(role),
                password,
            )
        )
        schema = sql.Identifier(embedding_table_config["target_schema"])
        conn.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(schema))
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
        conn.execute("DROP SCHEMA public CASCADE;")
        conn.execute("CREATE SCHEMA public")
        conn.execute("CREATE EXTENSION vector")

        conn.execute(
            sql.SQL("""
        CREATE TABLE {0}.{1} (
            {2}              SERIAL NOT NULL,
            {3}              SERIAL NOT NULL,
            content          TEXT NOT NULL,
            PRIMARY KEY ({2}, {3})
        )""").format(
                sql.Identifier(embedding_table_config["source_schema"]),
                sql.Identifier(embedding_table_config["source_table"]),
                sql.Identifier(embedding_table_config["source_pk"][0]["attname"]),
                sql.Identifier(embedding_table_config["source_pk"][1]["attname"]),
            )
        )

        conn.execute(
            sql.SQL("CREATE TABLE {} ({} INT, {} INT, queued_at timestamptz)").format(
                sql.Identifier(
                    embedding_table_config["queue_schema"],
                    embedding_table_config["queue_table"],
                ),
                sql.Identifier(embedding_table_config["source_pk"][0]["attname"]),
                sql.Identifier(embedding_table_config["source_pk"][1]["attname"]),
            )
        )

        conn.execute(
            sql.SQL("CREATE INDEX ON {}({}, {})").format(
                sql.Identifier(
                    embedding_table_config["queue_schema"],
                    embedding_table_config["queue_table"],
                ),
                sql.Identifier(embedding_table_config["source_pk"][0]["attname"]),
                sql.Identifier(embedding_table_config["source_pk"][1]["attname"]),
            )
        )

        conn.execute(
            sql.SQL("""
            CREATE TABLE {0} (
                chunk_id UUID PRIMARY KEY default gen_random_uuid(),
                {1} INT NOT NULL,
                {2} INT NOT NULL,
                chunk_seq INT NOT NULL,
                chunk TEXT,
                embedding VECTOR({3}),
                UNIQUE ({1}, {2}, chunk_seq),
                FOREIGN KEY ({1}, {2}) REFERENCES {4}.{5} ({6}, {7})
            )
            """).format(
                sql.Identifier(
                    embedding_table_config["target_schema"],
                    embedding_table_config["target_table"],
                ),
                sql.Identifier(embedding_table_config["source_pk"][0]["attname"]),
                sql.Identifier(embedding_table_config["source_pk"][1]["attname"]),
                DIMENSION_COUNT,
                sql.Identifier(embedding_table_config["source_schema"]),
                sql.Identifier(embedding_table_config["source_table"]),
                sql.Identifier(embedding_table_config["source_pk"][0]["attname"]),
                sql.Identifier(embedding_table_config["source_pk"][1]["attname"]),
            )
        )

        conn.execute("""
            create table ai.vectorizer_errors
            ( id int not null
            , message text
            , details jsonb
            , recorded timestamptz not null default now()
            );
        """)

        yield {
            "container": postgres_container,
            "conn": conn,
            "event_db_config": {
                "host": postgres_container._docker.host(),  # type: ignore
                "port": int(
                    postgres_container.get_exposed_port(postgres_container.port)
                ),
                "db_name": postgres_container.dbname,
                "ssl_mode": "disable",
                "role": role,
                "password": password,
            },
        }


@dataclass
class ItemFixture:
    pk_att_1: int
    pk_att_2: int
    content: str


@pytest.fixture
def items_fixtures(request: pytest.FixtureRequest) -> list[ItemFixture]:
    items_count = getattr(request, "param", 1)
    return [ItemFixture(i, i, f"post_{i}") for i in range(1, items_count + 1)]


@pytest.fixture
def db_with_data(
    db: dict[str, Any],
    embedding_table_config: dict[str, Any],
    items_fixtures: list[ItemFixture],
) -> dict[str, Any]:
    with db["conn"].cursor() as cursor:
        items = [[i.pk_att_1, i.pk_att_2, i.content] for i in items_fixtures]
        insert_source_query = sql.SQL(
            "INSERT INTO {}.{} ({}, {}, content) VALUES (%s, %s, %s)"
        ).format(
            sql.Identifier(embedding_table_config["source_schema"]),
            sql.Identifier(embedding_table_config["source_table"]),
            sql.Identifier(embedding_table_config["source_pk"][0]["attname"]),
            sql.Identifier(embedding_table_config["source_pk"][1]["attname"]),
        )
        if items:
            cursor.executemany(insert_source_query, items)

        work_items = [[i.pk_att_1, i.pk_att_2] for i in items_fixtures]
        if work_items:
            cursor.executemany(
                sql.SQL("INSERT INTO {} ({}, {}) values (%s, %s)").format(
                    sql.Identifier(
                        embedding_table_config["queue_schema"],
                        embedding_table_config["queue_table"],
                    ),
                    sql.Identifier(embedding_table_config["source_pk"][0]["attname"]),
                    sql.Identifier(embedding_table_config["source_pk"][1]["attname"]),
                ),
                work_items,
            )

        # This won't be put on the queue
        cursor.execute(insert_source_query, (-1, -1, "post_-1"))

    return db


@pytest.fixture(params=["openai"])
def embedding(request: pytest.FixtureRequest) -> dict[str, Any]:
    implementation = request.param
    embeddings = {
        "openai": {
            "implementation": "openai",
            "model": "text-embedding-ada-002",
            "api_key_name": "OPENAI_API_KEY",
        },
    }

    try:
        return embeddings[implementation]
    except KeyError as e:
        raise ValueError(f"Unknown embedding implementation: {implementation}") from e


@pytest.fixture(params=["character_text_splitter", "recursive_character_text_splitter"])
def chunking(request: pytest.FixtureRequest) -> dict[str, Any]:
    implementation = request.param
    chunkers = {
        "character_text_splitter": {
            "implementation": "character_text_splitter",
            "separator": "\n\n",
            "chunk_size": 128,
            "chunk_column": "content",
            "chunk_overlap": 10,
            "is_separator_regex": False,
        },
        "recursive_character_text_splitter": {
            "implementation": "recursive_character_text_splitter",
            "separators": ["\n\n"],
            "chunk_size": 128,
            "chunk_column": "content",
            "chunk_overlap": 10,
            "is_separator_regex": False,
        },
    }

    try:
        return chunkers[implementation]
    except KeyError as e:
        raise ValueError(f"Unknown chunking implementation: {implementation}") from e


@pytest.fixture(params=["chunk_value", "python_template"])
def formatting(request: pytest.FixtureRequest) -> dict[str, Any]:
    implementation = request.param
    formatters = {
        "python_template": {
            "implementation": "python_template",
            "template": "id: $id id2: $id2 $chunk",
        },
        "chunk_value": {"implementation": "chunk_value"},
    }

    try:
        return formatters[implementation]
    except KeyError as e:
        raise ValueError(f"Unknown formatting implementation: {implementation}") from e


@pytest.fixture
def concurrency():
    return 1


@pytest.fixture
def batch_size():
    return 1


@pytest.fixture
def base_event(
    embedding_table_config: dict[str, Any],
    embedding: dict[str, Any],
    chunking: dict[str, Any],
    formatting: dict[str, Any],
    concurrency: int,
    batch_size: int,
) -> dict[str, Any]:
    return {
        "payload": {
            "id": 1,
            "config": {
                "version": "0.1.0",
                "embedding": embedding,
                "chunking": chunking,
                "formatting": formatting,
                # We are not directly using scheduling but it helps us tests
                # that pydantic doesn't fail with the extra information in the
                # event payload.
                "scheduling": {
                    "job_id": 1000,
                    "timezone": "America/Chicago",
                    "config_type": "scheduling",
                    "initial_start": "2050-01-06T00:00:00+00:00",
                    "implementation": "timescaledb",
                    "schedule_interval": "00:05:00",
                },
                "processing": {
                    "config_type": "processing",
                    "implementation": "cloud_functions",
                    "batch_size": batch_size,
                    "concurrency": concurrency,
                    "log_level": "INFO",
                },
            },
            **embedding_table_config,
        },
        "update_embeddings": {
            "db": {
                "host": "localhost",
                "port": 5432,
                "role": "tsdbquerier",
                "db_name": "tsdb",
                "password": "my-password",
            },
            "secrets": {
                "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "my-secret"),
            },
        },
    }


@pytest.fixture
def event(
    db: dict[str, Any],
    base_event: dict[str, Any],
) -> dict[str, Any]:
    event = base_event.copy()
    event["update_embeddings"]["db"] = db["event_db_config"]
    return event
