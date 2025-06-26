import os
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock

from pgvector.psycopg import register_vector_async  # type: ignore
from psycopg import AsyncConnection, Connection, sql
from psycopg.rows import dict_row

from pgai.vectorizer import Executor, LoadingError, Vectorizer
from pgai.vectorizer.features.features import Features
from pgai.vectorizer.parsing import ParsingAuto
from pgai.vectorizer.worker_tracking import WorkerTracking
from tests.vectorizer.cli.conftest import (
    TestDatabase,
    configure_vectorizer,
    setup_source_table,
)

# ruff: noqa: E501


def setup_vectorizer(connection: Connection) -> Vectorizer:
    table_name = setup_source_table(connection, 1)

    vectorizer_id = configure_vectorizer(
        table_name,
        connection,
    )

    with connection.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "select pg_catalog.to_jsonb(v) as vectorizer from ai.vectorizer v where v.id = %s",
            (vectorizer_id,),
        )
        row = cur.fetchone()
        assert row is not None

        vectorizer = Vectorizer(**row["vectorizer"])
        return vectorizer


async def get_queue_table_items(
    aconn: AsyncConnection, vectorizer: Vectorizer
) -> list[dict[str, Any]]:
    async with aconn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            sql.SQL("SELECT * FROM {queue_table}").format(
                queue_table=sql.Identifier(
                    vectorizer.queue_schema, vectorizer.queue_table
                )
            )
        )
        return await cur.fetchall()


async def get_dlq_table_items(
    aconn: AsyncConnection, vectorizer: Vectorizer
) -> list[dict[str, Any]]:
    async with aconn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            sql.SQL("SELECT * FROM {queue_table}").format(
                queue_table=sql.Identifier(
                    vectorizer.queue_schema,
                    vectorizer.queue_failed_table,  # type: ignore
                )
            )
        )
        return await cur.fetchall()


async def get_advisory_locks(aconn: AsyncConnection) -> list[dict[str, Any]]:
    async with aconn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT * FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid()"
        )
        return await cur.fetchall()


async def get_vectorizer_errors(aconn: AsyncConnection) -> list[dict[str, Any]]:
    async with aconn.cursor(row_factory=dict_row) as cur:
        await cur.execute("SELECT * FROM ai.vectorizer_errors")
        return await cur.fetchall()


def assert_contains_only(
    objs: list[dict[Any, Any]], expected: dict[Any, Any] | list[dict[Any, Any]]
):
    if not isinstance(expected, list):
        expected = [expected]
    assert len(objs) == len(expected)
    for item in expected:
        assert_contains_multi(objs, item, 1)


def assert_contains(objs: list[dict[Any, Any]], expected: dict[Any, Any]):
    assert_contains_multi(objs, expected, 1)


def assert_contains_multi(
    objs: list[dict[Any, Any]], expected: dict[Any, Any], count: int
):
    assert (
        sum(all(obj.get(k) == v for k, v in expected.items()) for obj in objs) == count
    ), f"{objs} does not contain {expected} {count} times"


async def test_vectorizer_fetch_work_behaves_correctly_with_one_queue_item(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
):
    """Test that fetch_work correctly gets a single queue item"""
    _, connection = cli_db

    vectorizer = setup_vectorizer(connection)

    features = Features.for_testing_latest_version()
    worker_tracking = WorkerTracking(cli_db_url, 500, features, "0.0.1")
    executor = Executor(cli_db_url, vectorizer, features, worker_tracking)

    async with await AsyncConnection.connect(cli_db_url, autocommit=False) as aconn:
        queue_items = await get_queue_table_items(aconn, vectorizer)
        assert_contains_only(queue_items, {"id": 1, "attempts": 0, "retry_after": None})

        advisory_locks = await get_advisory_locks(aconn)
        assert len(advisory_locks) == 0

        result = await executor._fetch_work(aconn)  # type: ignore
        assert_contains_only(result, {"id": 1, "attempts": 1, "retry_after": None})

        queue_items = await get_queue_table_items(aconn, vectorizer)
        assert_contains_only(queue_items, {"id": 1, "attempts": 1, "retry_after": None})
        advisory_locks = await get_advisory_locks(aconn)
        assert len(advisory_locks) == 1


async def test_vectorizer_fetch_work_behaves_correctly_with_duplicate_queue_items(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
):
    """Test that fetch_work correctly removes duplicate items"""
    _, connection = cli_db

    vectorizer = setup_vectorizer(connection)

    with connection.cursor() as cur, connection.transaction():
        cur.execute(
            sql.SQL("INSERT INTO {queue_table} (id) VALUES (1)").format(
                queue_table=sql.Identifier(
                    vectorizer.queue_schema, vectorizer.queue_table
                )
            )
        )

    features = Features.for_testing_latest_version()
    worker_tracking = WorkerTracking(cli_db_url, 500, features, "0.0.1")
    executor = Executor(cli_db_url, vectorizer, features, worker_tracking)

    async with await AsyncConnection.connect(cli_db_url, autocommit=False) as aconn:
        queue_items = await get_queue_table_items(aconn, vectorizer)
        assert len(queue_items) == 2
        assert_contains_multi(
            queue_items, {"id": 1, "attempts": 0, "retry_after": None}, 2
        )

        advisory_locks = await get_advisory_locks(aconn)
        assert len(advisory_locks) == 0

        result = await executor._fetch_work(aconn)  # type: ignore
        assert_contains_only(result, {"id": 1, "attempts": 1, "retry_after": None})

        queue_items = await get_queue_table_items(aconn, vectorizer)
        assert_contains_only(queue_items, {"id": 1, "attempts": 1, "retry_after": None})
        advisory_locks = await get_advisory_locks(aconn)
        assert len(advisory_locks) == 1


async def test_vectorizer_fetch_work_adheres_to_configured_batch_size(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
):
    """Test that fetch_work correctly handles duplicates when more items available than the batch size"""
    _, connection = cli_db

    vectorizer = setup_vectorizer(connection)
    vectorizer.config.processing.batch_size = 2

    queue_table = sql.Identifier(vectorizer.queue_schema, vectorizer.queue_table)

    with connection.cursor() as cur, connection.transaction():
        cur.executemany(
            sql.SQL(
                "INSERT INTO {source_table}(id, id2, content) VALUES (%s, %s, %s)"
            ).format(
                source_table=sql.Identifier(
                    vectorizer.source_schema, vectorizer.source_table
                )
            ),
            [(i, i, f"post_{i}") for i in range(2, 11)],
        )
        # insert a duplicate queue item for every post
        cur.executemany(
            sql.SQL("INSERT INTO {queue_table}(id, attempts) VALUES (%s, 2)").format(
                queue_table=queue_table
            ),
            [(i,) for i in range(1, 11)],
        )

    features = Features.for_testing_latest_version()
    worker_tracking = WorkerTracking(cli_db_url, 500, features, "0.0.1")
    executor = Executor(cli_db_url, vectorizer, features, worker_tracking)

    async with await AsyncConnection.connect(cli_db_url, autocommit=False) as aconn:
        queue_items = await get_queue_table_items(aconn, vectorizer)
        assert len(queue_items) == 20
        advisory_locks = await get_advisory_locks(aconn)
        assert len(advisory_locks) == 0

        result = await executor._fetch_work(aconn)  # type: ignore
        assert len(result) == 2
        assert_contains(result, {"id": 1, "attempts": 3, "retry_after": None})
        assert_contains(result, {"id": 2, "attempts": 3, "retry_after": None})

        queue_items = await get_queue_table_items(aconn, vectorizer)
        assert len(queue_items) == 18
        advisory_locks = await get_advisory_locks(aconn)
        assert len(advisory_locks) == 2


async def test_vectorizer_error_handling_updates_retry_after_and_stores_error_before_max_attempts_reached(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
):
    """Test that error handling correctly updates the retry_after field and stores an error"""
    _, connection = cli_db

    vectorizer = setup_vectorizer(connection)

    features = Features.for_testing_latest_version()
    worker_tracking = WorkerTracking(cli_db_url, 500, features, "0.0.1")
    executor = Executor(cli_db_url, vectorizer, features, worker_tracking)

    async with (
        await AsyncConnection.connect(cli_db_url, autocommit=False) as aconn,
        aconn.transaction(),
    ):
        queue_items = await get_queue_table_items(aconn, vectorizer)
        assert_contains_only(
            queue_items,
            {
                "id": 1,
                "attempts": 0,
                "retry_after": None,
            },
        )

        result = await executor._fetch_work(aconn)  # type: ignore

        queue_items = await get_queue_table_items(aconn, vectorizer)
        assert_contains_only(queue_items, {"id": 1, "attempts": 1, "retry_after": None})

        errors = [(item, LoadingError(e=RuntimeError("whoops"))) for item in result]
        await executor._handle_errors(aconn, errors)  # type: ignore

        async with aconn.cursor() as cur:
            await cur.execute("SELECT now()")
            now: datetime = (await cur.fetchone())[0]  # type: ignore

        queue_items = await get_queue_table_items(aconn, vectorizer)
        assert_contains_only(
            queue_items,
            {"id": 1, "attempts": 1, "retry_after": now + timedelta(minutes=3)},
        )

        vectorizer_errors = await get_vectorizer_errors(aconn)
        assert_contains_only(
            vectorizer_errors,
            {
                "details": {
                    "error_reason": "whoops",
                    "step": "loading",
                },
                "id": 1,
                "message": "loading failed",
                "name": "public_blog_embedding_store",
                "recorded": now,
            },
        )


async def test_vectorizer_error_handling_moves_failed_items_to_dlq_and_logs_error_after_max_attempts_reached(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
):
    """Test that error handling moves "permanently failed" items to the dead-letter-queue"""
    _, connection = cli_db

    vectorizer = setup_vectorizer(connection)

    features = Features.for_testing_latest_version()
    worker_tracking = WorkerTracking(cli_db_url, 500, features, "0.0.1")
    executor = Executor(cli_db_url, vectorizer, features, worker_tracking)

    with connection.cursor() as cur, connection.transaction():
        cur.execute(
            sql.SQL("UPDATE {queue_table} SET attempts = 6").format(
                queue_table=sql.Identifier(
                    vectorizer.queue_schema, vectorizer.queue_table
                )
            )
        )

    async with (
        await AsyncConnection.connect(cli_db_url, autocommit=False) as aconn,
        aconn.transaction(),
    ):
        queue_items = await get_queue_table_items(aconn, vectorizer)
        assert_contains_only(
            queue_items,
            {
                "id": 1,
                "attempts": 6,
                "retry_after": None,
            },
        )

        result = await executor._fetch_work(aconn)  # type: ignore

        queue_items = await get_queue_table_items(aconn, vectorizer)
        assert_contains_only(queue_items, {"id": 1, "attempts": 7, "retry_after": None})

        errors = [(item, LoadingError(e=RuntimeError("whoops"))) for item in result]
        await executor._handle_errors(aconn, errors)  # type: ignore

        async with aconn.cursor() as cur:
            await cur.execute("SELECT now()")
            now: datetime = (await cur.fetchone())[0]  # type: ignore

        queue_items = await get_queue_table_items(aconn, vectorizer)
        assert len(queue_items) == 0

        dlq_items = await get_dlq_table_items(aconn, vectorizer)
        assert_contains_only(
            dlq_items,
            {
                "id": 1,
                "failure_step": "loading",
                "created_at": now,
                "attempts": 7,
            },
        )

        vectorizer_errors = await get_vectorizer_errors(aconn)
        assert_contains_only(
            vectorizer_errors,
            {
                "details": {
                    "error_reason": "whoops",
                    "step": "loading",
                },
                "id": 1,
                "message": "loading failed",
                "name": "public_blog_embedding_store",
                "recorded": now,
            },
        )


async def test_vectorizer_unlocks_advisory_locks_on_successful_processing(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that error handling moves "permanently failed" items to the dead-letter-queue"""
    _, connection = cli_db

    vectorizer = setup_vectorizer(connection)
    vectorizer.config.embedding.set_api_key(  # type: ignore
        {"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")}
    )

    features = Features.for_testing_latest_version()
    worker_tracking = WorkerTracking(cli_db_url, 500, features, "0.0.1")
    executor = Executor(cli_db_url, vectorizer, features, worker_tracking)

    with vcr_.use_cassette(
        "test_vectorizer_unlocks_advisory_locks_on_successful_processing.yaml"
    ):
        async with await AsyncConnection.connect(cli_db_url, autocommit=False) as conn:
            async with conn.transaction():
                queue_items = await get_queue_table_items(conn, vectorizer)
                assert_contains_only(
                    queue_items,
                    {
                        "id": 1,
                        "attempts": 0,
                        "retry_after": None,
                    },
                )

                advisory_locks = await get_advisory_locks(conn)
                assert len(advisory_locks) == 0

                await register_vector_async(conn)

            # note: we can't perform this test on executor.run() because that closes
            # the connection when it's done, hence unlocking advisory locks.
            result = await executor._do_batch(conn)  # type: ignore
            assert result == 1

            queue_items = await get_queue_table_items(conn, vectorizer)
            assert len(queue_items) == 0

            advisory_locks = await get_advisory_locks(conn)
            assert len(advisory_locks) == 0


async def test_vectorizer_unlocks_advisory_locks_on_failed_processing(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    vcr_: Any,
):
    """Test that error handling moves "permanently failed" items to the dead-letter-queue"""
    _, connection = cli_db

    vectorizer = setup_vectorizer(connection)
    vectorizer.config.embedding.set_api_key(  # type: ignore
        {"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")}
    )

    mock_parsing = Mock(spec=ParsingAuto)
    mock_parsing.implementation = "auto"
    mock_parsing.parse.side_effect = RuntimeError("parsing failed")

    # Rebuild the config with the mock parsing
    vectorizer.config = vectorizer.config.model_copy(update={"parsing": mock_parsing})

    features = Features.for_testing_latest_version()
    worker_tracking = WorkerTracking(cli_db_url, 500, features, "0.0.1")
    executor = Executor(cli_db_url, vectorizer, features, worker_tracking)

    with vcr_.use_cassette(
        "test_vectorizer_unlocks_advisory_locks_on_successful_processing.yaml"
    ):
        async with await AsyncConnection.connect(cli_db_url, autocommit=False) as conn:
            async with conn.transaction():
                queue_items = await get_queue_table_items(conn, vectorizer)
                assert_contains_only(
                    queue_items,
                    {
                        "id": 1,
                        "attempts": 0,
                        "retry_after": None,
                    },
                )

                advisory_locks = await get_advisory_locks(conn)
                assert len(advisory_locks) == 0

                await register_vector_async(conn)

            # note: we can't perform this test on executor.run() because that closes
            # the connection when it's done, hence unlocking advisory locks.
            result = await executor._do_batch(conn)  # type: ignore
            assert result == 1

            queue_items = await get_queue_table_items(conn, vectorizer)
            assert len(queue_items) == 1

            advisory_locks = await get_advisory_locks(conn)
            assert len(advisory_locks) == 0

            errors = await get_vectorizer_errors(conn)
            assert_contains_only(
                errors,
                {
                    "details": {
                        "error_reason": "parsing failed",
                        "step": "parsing",
                    },
                    "id": 1,
                    "message": "parsing failed",
                    "name": "public_blog_embedding_store",
                },
            )
