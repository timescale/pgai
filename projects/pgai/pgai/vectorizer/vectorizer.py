import asyncio
import json
import os
import sys
import threading
import time
from collections.abc import AsyncGenerator, Callable, Sequence
from functools import cache, cached_property, partial
from itertools import islice
from typing import Any, TypeAlias, TypeVar
from uuid import UUID

import psycopg
import structlog
from ddtrace.trace import tracer
from pgvector.psycopg import register_vector_async  # type: ignore
from psycopg import AsyncConnection, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb, set_json_dumps
from pydantic import BaseModel, Field, model_validator
from pydantic_core._pydantic_core import ArgsKwargs
from typing_extensions import override

from .chunking import (
    LangChainCharacterTextSplitter,
    LangChainRecursiveCharacterTextSplitter,
    NoneChunker,
)
from .destination import ColumnDestination, TableDestination
from .embedders import LiteLLM, Ollama, OpenAI, VoyageAI
from .features import Features
from .formatting import ChunkValue, PythonTemplate
from .loading import ColumnLoading, LoadingError, UriLoading
from .migrations import apply_migrations
from .parsing import ParsingAuto, ParsingNone, ParsingPyMuPDF
from .processing import ProcessingDefault
from .worker_tracking import WorkerTracking

logger = structlog.get_logger()

VectorizerErrorRecord: TypeAlias = tuple[int, str, Jsonb]
EmbeddingRecord: TypeAlias = list[Any]
SourceRow: TypeAlias = dict[str, Any]

DEFAULT_CONCURRENCY = 1
DEFAULT_VECTORIZER_ERRORS_TABLE = "_vectorizer_errors"

VECTORIZER_FAILED = "vectorizer failed with unexpected error"

if sys.version_info >= (3, 11):
    from builtins import BaseExceptionGroup
else:
    # For Python 3.10 and below, use the backport
    from exceptiongroup import BaseExceptionGroup


class EmbeddingProviderError(Exception):
    """
    Raised when an embedding provider API request fails.
    """

    msg = "embedding provider failed"


class PkAtt(BaseModel):
    """
    Represents an attribute of a primary key.

    Attributes:
        attname (str): The name of the attribute (column).
    """

    attname: str
    pknum: int
    attnum: int


class Config(BaseModel):
    """
    Holds the configuration for the vectorizer including embedding, processing,
    chunking, and formatting.

    Attributes:
        version: The version of the configuration.
        embedding: The embedding's provider configuration.
        processing: Processing settings such as batch size and concurrency.
        chunking: The chunking strategy.
        formatting: Formatting strategy to apply to the chunks.
    """

    version: str
    # Set in the migrations if the configuration is migrated to a newer version
    original_version: str | None = None
    loading: ColumnLoading | UriLoading
    embedding: OpenAI | Ollama | VoyageAI | LiteLLM
    processing: ProcessingDefault
    destination: TableDestination | ColumnDestination = Field(
        ..., discriminator="implementation"
    )
    chunking: (
        LangChainCharacterTextSplitter
        | LangChainRecursiveCharacterTextSplitter
        | NoneChunker
    ) = Field(..., discriminator="implementation")
    formatting: PythonTemplate | ChunkValue = Field(..., discriminator="implementation")
    parsing: ParsingNone | ParsingAuto | ParsingPyMuPDF = Field(
        default_factory=lambda: ParsingAuto(implementation="auto"),
        discriminator="implementation",
    )


class Vectorizer(BaseModel):
    """
    Represents a vectorizer configuration that processes data from a source
    table to generate embeddings.

    Attributes:
        id (int): The unique identifier of the vectorizer.
        config (Config): The configuration object for the vectorizer.
        queue_table (str): The name of the queue table.
        queue_schema (str): The schema where the queue table is located.
        source_schema (str): The schema of the source table.
        source_table (str): The source table where the data comes from.
        target_schema (str): The schema of the target table where embeddings are saved.
        target_table (str): The target table where embeddings are saved.
        source_pk (list[PkAtt]): List of primary key attributes from the source table.
        errors_schema (str): The schema where the error log is saved. Default is "ai".
        errors_table (str): The table where errors are logged.
    """

    id: int
    config: Config
    queue_schema: str
    queue_table: str
    source_schema: str
    source_table: str
    source_pk: list[PkAtt]
    queue_failed_table: str | None = None
    errors_schema: str = "ai"
    errors_table: str = DEFAULT_VECTORIZER_ERRORS_TABLE
    schema_: str = Field(alias="schema", default="ai")
    table: str = "vectorizer"

    async def run(
        self,
        db_url: str,
        features: Features,
        worker_tracking: WorkerTracking,
        concurrency: int | None = None,
        should_continue_processing_hook: None | Callable[[int, int], bool] = None,
    ) -> int:
        """Run this vectorizer with the specified configuration using Worker instances

        Args:
            db_url: Database connection URL
            features: Features from database
            worker_tracking: Tracking instance for worker stats
            concurrency: Number of concurrent workers
                (overrides vectorizer config if provided)
            should_continue_processing_hook: Optional callback to
                control processing flow

        Returns:
            Number of items processed
        """

        if (
            self.errors_table == DEFAULT_VECTORIZER_ERRORS_TABLE
            and not features.has_vectorizer_errors_view
        ):
            self.errors_table = "vectorizer_errors"

        concurrency = concurrency or self.config.processing.concurrency
        tasks = [
            asyncio.create_task(
                Executor(
                    db_url,
                    self,
                    features,
                    worker_tracking,
                    should_continue_processing_hook,
                ).run()
            )
            for _ in range(concurrency)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # raise any exceptions, but only after all tasks have completed
        items: int = 0
        exceptions: list[BaseException] = []
        for result in results:
            if isinstance(result, BaseException):
                # report all exceptions. Doesn't log, it just stores in the DB.
                await worker_tracking.save_vectorizer_error(self.id, str(result))
                exceptions.append(result)
            else:
                items += result

        logger.info(
            "finished processing vectorizer", items=items, vectorizer_id=self.id
        )

        if len(exceptions) > 0:
            raise BaseExceptionGroup("vectorizer finished with errors", exceptions)

        return items

    @model_validator(mode="before")
    @classmethod
    def migrate_config_to_new_version(cls, data: Any) -> Any:
        if not data:
            return data
        if isinstance(data, ArgsKwargs) and data.kwargs is not None:
            return apply_migrations(data.kwargs)
        if isinstance(data, dict) and all(isinstance(key, str) for key in data):  # type: ignore[reportUnknownVariableType]
            return apply_migrations(data)  # type: ignore[arg-type]

        logger.warning("Unable to migrate configuration: raw data type is unknown")
        return data  # type: ignore[reportUnknownVariableType]


class VectorizerQueryBuilder:
    """
    A query builder class for generating SQL queries related to the vectorizer
    operations.

    Attributes:
        vectorizer (Vectorizer): The vectorizer for which queries are built.
    """

    def __init__(self, vectorizer: Vectorizer):
        self.vectorizer = vectorizer

    @property
    def pk_fields_sql(self) -> sql.Composed:
        """Generates the SQL expression for a comma separated list of the
        attributes of a primary key. For example, if the primary key has 2
        fields (author, title), it will return a sql.Composed object that
        represents the SQL expression "author, title". The columns will be
        listed in the order they appear in the table NOT the primary key.
        """
        return sql.SQL(" ,").join(
            [
                sql.Identifier(a.attname)
                for a in sorted(self.vectorizer.source_pk, key=lambda pk: pk.attnum)
            ]
        )

    @cached_property
    def pk_attnames(self) -> list[str]:
        """
        Returns a list of primary key attribute names. For example, if the
        primary key has 2 fields (author, title), it will return ["author", "title"].
        The columns will be listed in the order they appear in the table NOT the
        primary key.
        """
        return [
            a.attname
            for a in sorted(self.vectorizer.source_pk, key=lambda pk: pk.attnum)
        ]

    @property
    def pk_fields(self) -> list[sql.Identifier]:
        """
        Returns the SQL identifiers for primary key fields.
        The columns will be listed in the order they appear in the table NOT the
        primary key.
        """
        return [
            sql.Identifier(a.attname)
            for a in sorted(self.vectorizer.source_pk, key=lambda pk: pk.attnum)
        ]

    @cache  # noqa: B019
    def target_table_ident(self, destination: TableDestination) -> sql.Identifier:
        """
        Returns the SQL identifier for the fully qualified name of the target table.
        """
        return sql.Identifier(
            destination.target_schema,
            destination.target_table,
        )

    @property
    def source_table_ident(self) -> sql.Identifier:
        """
        Returns the SQL identifier for the fully qualified name of the source table.
        """
        return sql.Identifier(
            self.vectorizer.source_schema, self.vectorizer.source_table
        )

    @property
    def errors_table_ident(self) -> sql.Identifier:
        """
        Returns the SQL identifier for the fully qualified name of the errors table.
        """
        return sql.Identifier(
            self.vectorizer.errors_schema, self.vectorizer.errors_table
        )

    @property
    def queue_table_ident(self) -> sql.Identifier:
        """
        Returns the SQL identifier for the fully qualified name of the queue table.
        """
        return sql.Identifier(self.vectorizer.queue_schema, self.vectorizer.queue_table)

    @property
    def vectorizer_table_ident(self) -> sql.Identifier:
        """
        Returns the SQL identifier for the fully qualified name of the
        vectorizer table.
        """
        return sql.Identifier(self.vectorizer.schema_, self.vectorizer.table)

    @cached_property
    def fetch_work_query(self) -> sql.Composed:
        """
        Generates the SQL query to fetch work items from the queue table.

        The query is safe to run concurrently from multiple workers. It handles
        duplicate work items by allowing only one instance of the duplicates to
        be proccessed at a time.

        For a thorough explanation of the query, see:

        https://www.timescale.com/blog/how-we-designed-a-resilient-vector-embedding-creation-system-for-postgresql-data/#process-the-work-queue

        The main takeaways are:

        > ... the system retrieves a specified number of entries from the work
        queue, determined by the batch queue size parameter. A FOR UPDATE lock
        is taken to ensure that concurrently executing scripts don’t try
        processing the same queue items. The SKIP LOCKED directive ensures that
        if any entry is currently being handled by another script, the system
        will skip it instead of waiting, avoiding unnecessary delays.

        > Due to the possibility of duplicate entries for the same blog_id
        within the work-queue table, simply locking said table is insufficient
        ... A Postgres advisory lock, prefixed with the table identifier to
        avoid potential overlaps with other such locks, is employed. The try
        variant, analogous to the earlier application of SKIP LOCKED, ensures
        the system avoids waiting on locks. The inclusion of the ORDER BY
        blog_id clause helps prevent potential deadlocks...

        The only differece, between the blog and this query, is that we handle
        composite primary keys.
        """
        return sql.SQL("""
                WITH selected_rows AS (
                    SELECT {pk_fields}
                    FROM {queue_table}
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                ),
                locked_items AS (
                    SELECT
                        {pk_fields},
                        pg_try_advisory_xact_lock(
                            %s,
                            hashtext(concat_ws('|', {lock_fields}))
                        ) AS locked
                    FROM (
                        SELECT DISTINCT {pk_fields}
                        FROM selected_rows
                        ORDER BY {pk_fields}
                    ) as ids
                ),
                deleted_rows AS (
                    DELETE FROM {queue_table} AS w
                    USING locked_items AS l
                    WHERE l.locked = true
                    AND {delete_join_predicates}
                )
                SELECT s.*
                FROM locked_items l
                LEFT JOIN LATERAL ( -- NOTE: lateral join forces runtime chunk exclusion
                    SELECT *
                    FROM {source_schema}.{source_table} s
                    WHERE {lateral_join_predicates}
                    LIMIT 1
                ) AS s ON true
                WHERE l.locked = true
                ORDER BY {pk_fields}
                        """).format(
            pk_fields=self.pk_fields_sql,
            queue_table=sql.Identifier(
                self.vectorizer.queue_schema, self.vectorizer.queue_table
            ),
            lock_fields=sql.SQL(" ,").join(
                [
                    xs
                    for x in self.vectorizer.source_pk
                    for xs in [
                        sql.Literal(x.attname),
                        sql.Identifier(x.attname),
                    ]
                ]
            ),
            delete_join_predicates=sql.SQL(" AND ").join(
                [
                    sql.SQL("w.{} = l.{}").format(
                        sql.Identifier(x.attname),
                        sql.Identifier(x.attname),
                    )
                    for x in self.vectorizer.source_pk
                ]
            ),
            source_schema=sql.Identifier(self.vectorizer.source_schema),
            source_table=sql.Identifier(self.vectorizer.source_table),
            lateral_join_predicates=sql.SQL(" AND ").join(
                [
                    sql.SQL("l.{} = s.{}").format(
                        sql.Identifier(x.attname),
                        sql.Identifier(x.attname),
                    )
                    for x in self.vectorizer.source_pk
                ]
            ),
        )

    @cached_property
    def fetch_work_query_with_retries(self) -> sql.Composed:
        """
        Note that this is an updated version of the original query that includes
        the loading_retries column.
        Generates the SQL query to fetch work items from the queue table.

        The query is safe to run concurrently from multiple workers. It handles
        duplicate work items by allowing only one instance of the duplicates to
        be proccessed at a time.

        For a thorough explanation of the query, see:

        https://www.timescale.com/blog/how-we-designed-a-resilient-vector-embedding-creation-system-for-postgresql-data/#process-the-work-queue

        The main takeaways are:

        > ... the system retrieves a specified number of entries from the work
        queue, determined by the batch queue size parameter. A FOR UPDATE lock
        is taken to ensure that concurrently executing scripts don't try
        processing the same queue items. The SKIP LOCKED directive ensures that
        if any entry is currently being handled by another script, the system
        will skip it instead of waiting, avoiding unnecessary delays.

        > Due to the possibility of duplicate entries for the same blog_id
        within the work-queue table, simply locking said table is insufficient
        ... A Postgres advisory lock, prefixed with the table identifier to
        avoid potential overlaps with other such locks, is employed. The try
        variant, analogous to the earlier application of SKIP LOCKED, ensures
        the system avoids waiting on locks. The inclusion of the ORDER BY
        blog_id clause helps prevent potential deadlocks...

        The only difference, between the blog and this query, is that we handle
        composite primary keys.
        """
        return sql.SQL("""
                WITH selected_rows AS (
                    SELECT {pk_fields}, {loading_retries}
                    FROM {queue_table}
                    WHERE loading_retry_after is null or loading_retry_after < now()
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                ),
                locked_items AS (
                    SELECT
                        {pk_fields}, {loading_retries},
                        pg_try_advisory_xact_lock(
                            %s,
                            hashtext(concat_ws('|', {lock_fields}))
                        ) AS locked
                    FROM (
                        SELECT DISTINCT {pk_fields}, {loading_retries}
                        FROM selected_rows
                        ORDER BY {pk_fields}
                    ) as ids
                ),
                deleted_rows AS (
                    DELETE FROM {queue_table} AS w
                    USING locked_items AS l
                    WHERE l.locked = true
                    AND {delete_join_predicates}
                )
                SELECT s.*, {loading_retries}
                FROM locked_items l
                LEFT JOIN LATERAL ( -- NOTE: lateral join forces runtime chunk exclusion
                    SELECT *
                    FROM {source_schema}.{source_table} s
                    WHERE {lateral_join_predicates}
                    LIMIT 1
                ) AS s ON true
                WHERE l.locked = true
                ORDER BY {pk_fields}
                        """).format(
            pk_fields=self.pk_fields_sql,
            loading_retries=sql.Identifier("loading_retries"),
            queue_table=sql.Identifier(
                self.vectorizer.queue_schema, self.vectorizer.queue_table
            ),
            lock_fields=sql.SQL(" ,").join(
                [
                    xs
                    for x in self.vectorizer.source_pk
                    for xs in [
                        sql.Literal(x.attname),
                        sql.Identifier(x.attname),
                    ]
                ]
            ),
            delete_join_predicates=sql.SQL(" AND ").join(
                [
                    sql.SQL("w.{} = l.{}").format(
                        sql.Identifier(x.attname),
                        sql.Identifier(x.attname),
                    )
                    for x in self.vectorizer.source_pk
                ]
            ),
            source_schema=sql.Identifier(self.vectorizer.source_schema),
            source_table=sql.Identifier(self.vectorizer.source_table),
            lateral_join_predicates=sql.SQL(" AND ").join(
                [
                    sql.SQL("l.{} = s.{}").format(
                        sql.Identifier(x.attname),
                        sql.Identifier(x.attname),
                    )
                    for x in self.vectorizer.source_pk
                ]
            ),
        )

    @cached_property
    def fetch_queue_table_oid_query(self) -> sql.Composed:
        return sql.SQL("SELECT to_regclass('{}')::oid").format(
            sql.Identifier(self.vectorizer.queue_schema, self.vectorizer.queue_table)
        )

    def delete_embeddings_query(
        self, items_count: int, destination: TableDestination
    ) -> sql.Composed:
        return sql.SQL("DELETE FROM {} WHERE ({}) IN ({})").format(
            self.target_table_ident(destination),  # type: ignore
            self.pk_fields_sql,
            self._pks_placeholders_tuples(items_count),
        )

    @cache  # noqa: B019
    def copy_embeddings_query(self, destination: TableDestination) -> sql.Composed:
        return sql.SQL(
            "COPY {} ({}, chunk_seq, chunk, embedding) FROM STDIN WITH (FORMAT BINARY)"
        ).format(self.target_table_ident(destination), self.pk_fields_sql)  # type: ignore

    @cache  # noqa: B019
    def update_embedding_query(self, destination: ColumnDestination) -> sql.Composed:
        """Returns a SQL query to update the embedding column (for ColumnDestination)"""
        return sql.SQL("UPDATE {} SET {} = %s WHERE ({}) = ({})").format(
            self.source_table_ident,
            sql.Identifier(destination.embedding_column),
            self.pk_fields_sql,
            sql.SQL(", ").join([sql.Placeholder() for _ in self.pk_fields]),
        )

    @cached_property
    def insert_errors_query(self) -> sql.Composed:
        return sql.SQL(
            "INSERT INTO {} (id, message, details) VALUES (%s, %s, %s)"
        ).format(
            self.errors_table_ident,
        )

    def _pks_placeholders_tuples(self, items_count: int) -> sql.Composed:
        """Generates a comma separated list of tuples with placeholders for the
        primary key fields of the source table.

        If the primary key has 2 fields, and we want to generate the
        placeholders to match against 3 items:

        self._pks_placeholders_tuples(3)
        # => "(%s, %s), (%s, %s), (%s, %s)"

        This can be used for queries like:

        DELETE FROM table WHERE (pk1, pk2) IN ((%s, %s), (%s, %s), (%s, %s))

        We cannot use ANY = %s because Postgres doesn't allow it for anonymous
        composite values.
        """
        placeholder_tuple = sql.SQL(", ").join(
            sql.Placeholder() for _ in range(len(self.vectorizer.source_pk))
        )

        tuples = sql.SQL(",").join(
            sql.SQL("({})").format(placeholder_tuple) for _ in range(items_count)
        )
        return tuples

    @cached_property
    def is_vectorizer_disabled_query(self) -> sql.Composed:
        return sql.SQL("SELECT disabled FROM {} WHERE id = %s").format(
            self.vectorizer_table_ident,
        )

    @cached_property
    def reinsert_work_to_retry_query(self) -> sql.Composed:
        return sql.SQL("""
            INSERT INTO {queue_table}
                ({pk_fields}, loading_retries, loading_retry_after)
            VALUES
                ({pk_values}, (%(loading_retries)s+1),
                now() + INTERVAL '3 minutes'* (%(loading_retries)s + 1))
                        """).format(
            pk_fields=self.pk_fields_sql,
            queue_table=sql.Identifier(
                self.vectorizer.queue_schema, self.vectorizer.queue_table
            ),
            pk_values=sql.SQL(",").join(
                sql.SQL("(%(pk{})s)").format(sql.Literal(i))
                for i in range(len(self.pk_fields))
            ),
        )

    @cached_property
    def insert_queue_failed_query(self) -> sql.Composed:
        return sql.SQL("""
            INSERT INTO {queue_failed_table}
                ({pk_fields}, failure_step)
            VALUES
                ({pk_values}, %(failure_step)s)""").format(
            queue_failed_table=sql.Identifier(
                self.vectorizer.queue_schema,
                self.vectorizer.queue_failed_table,  # type: ignore
            ),
            pk_fields=self.pk_fields_sql,
            pk_values=sql.SQL(",").join(
                sql.SQL("(%(pk{})s)").format(sql.Literal(i))
                for i in range(len(self.pk_fields))
            ),
        )


class ProcessingStats:
    """
    Tracks processing statistics for chunk processing tasks.

    Records the total processing time, number of chunks processed,
    and wall time. It also logs statistics such as chunks processed per second.

    Attributes:
        total_processing_time (float): The total time spent processing chunks.
        total_chunks (int): The total number of chunks processed.
        wall_time (float): The total wall time from when processing started.
        wall_start (float): The time when processing started, used for
            calculating the elapsed time.
    """

    total_processing_time: float
    total_chunks: int
    wall_time: float
    wall_start: float

    def __new__(cls):
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)

            logger.debug(
                "ProcessingStats initialized",
                thread_id=threading.get_native_id(),
                active_count=threading.active_count(),
                task=id(asyncio.current_task()),
            )
            cls._instance.total_processing_time = 0.0
            cls._instance.total_chunks = 0
            cls._instance.wall_start = time.perf_counter()
        return cls._instance

    def add_request_time(self, duration: float, chunk_count: int):
        """
        Adds the time and chunk count of a processing request to the accumulated totals.

        Args:
            duration (float): The time taken for the request.
            chunk_count (int): The number of chunks processed in the request.
        """
        self.total_processing_time += duration
        self.total_chunks += chunk_count

    async def print_stats(self):
        """
        Logs the processing statistics, including total time, chunks processed,
        and chunks processed per second.

        This method calculates two main rates:
        - Chunks processed per second overall.
        - Chunks processed per second per thread.

        The statistics are logged only to the DEBUG log level.
        """
        chunks_per_second_per_thread = (
            self.total_chunks / self.total_processing_time
            if self.total_processing_time > 0
            else 0
        )
        wall_time = time.perf_counter() - self.wall_start
        chunks_per_second = self.total_chunks / wall_time if wall_time > 0 else 0
        await logger.adebug(
            "Processing stats",
            wall_time=wall_time,
            total_processing_time=self.total_processing_time,
            total_chunks=self.total_chunks,
            chunks_per_second=chunks_per_second,
            chunks_per_second_per_thread=chunks_per_second_per_thread,
            task=id(asyncio.current_task()),
        )


T = TypeVar("T")


def flexible_take(iterable: list[T]) -> Callable[[int], list[T]]:
    """Creates a function that takes n elements from the iterable each time
    it's called."""
    # Convert to iterator if it's not already one
    iterator = iter(iterable)

    def take(n: int):
        # Convert to list so we get exactly what was requested
        return list(islice(iterator, n))

    return take


class UUIDEncoder(json.JSONEncoder):
    """A JSON encoder which can dump UUID."""

    @override
    def default(self, o: Any):
        if isinstance(o, UUID):
            return str(o)
        return json.JSONEncoder.default(self, o)


class Executor:
    """
    Responsible for processing items from the work queue and generating embeddings.

    The Executor fetches tasks from a database queue table, processes them using
    the vectorizer, and writes the resulting embeddings or errors back to the
    database.

    Attributes:
        db_url (str): The URL of the database to connect to.
        vectorizer (Vectorizer): The vectorizer configuration used for processing.
        queries (VectorizerQueryBuilder): A query builder instance used for
            generating SQL queries.
    """

    _queue_table_oid = None
    _should_continue_processing_hook: Callable[[int, int], bool]

    def __init__(
        self,
        db_url: str,
        vectorizer: Vectorizer,
        features: Features,
        worker_tracking: WorkerTracking,
        should_continue_processing_hook: None | Callable[[int, int], bool] = None,
    ):
        self.db_url = db_url
        self.vectorizer = vectorizer
        self.queries = VectorizerQueryBuilder(vectorizer)
        self._should_continue_processing_hook = should_continue_processing_hook or (
            lambda _loops, _res: True
        )
        self.features = features
        self.copy_types: None | Sequence[int] = None
        self.worker_tracking = worker_tracking

    async def run(self) -> int:
        """
        Embedding loop. Continuously fetches tasks from the work queue and
        processes them within the context of a transaction.

        Returns:
            int: The number of tasks processed from the work queue.
        """
        res = 0
        loops = 0

        async with await psycopg.AsyncConnection.connect(
            self.db_url,
            autocommit=True,
            application_name=f"pgai-worker[{self.vectorizer.id}]: {self.worker_tracking.get_short_worker_id()}",  # noqa: E501
        ) as conn:
            try:
                set_json_dumps(partial(json.dumps, cls=UUIDEncoder), context=conn)
                await register_vector_async(conn)
                await self.vectorizer.config.embedding.setup()
                while True:
                    if not await self._should_continue_processing(conn, loops, res):
                        return res
                    items_processed = await self._do_batch(conn)
                    if items_processed == 0:
                        return res
                    res += items_processed
                    loops += 1
                    await self.worker_tracking.save_vectorizer_success(
                        conn, self.vectorizer.id, items_processed
                    )
            except EmbeddingProviderError as e:
                async with conn.transaction():
                    await self._insert_vectorizer_error(
                        conn,
                        (
                            self.vectorizer.id,
                            e.msg,
                            Jsonb(
                                {
                                    "provider": self.vectorizer.config.embedding.implementation,  # noqa
                                    "error_reason": str(e.__cause__),
                                }
                            ),
                        ),
                    )

                if e.__cause__ is not None:
                    raise e.__cause__  # noqa
                raise e

            except Exception as e:
                async with conn.transaction():
                    await self._insert_vectorizer_error(
                        conn,
                        (
                            self.vectorizer.id,
                            VECTORIZER_FAILED,
                            Jsonb({"error_reason": str(e)}),
                        ),
                    )
                raise e

    async def _should_continue_processing(
        self, conn: AsyncConnection, loops: int, res: int
    ) -> bool:
        """Determine whether to continue processing based on vectorizer status
        and custom logic.

        Args:
            conn (AsyncConnection): Database connection for checking vectorizer status.
            loops (int): Number of processing loops completed.
            res (int): Result from the previous processing iteration.

        Returns:
            bool: True if processing should continue, False otherwise.

        Raises:
            Exception: If the vectorizer row is not found in the database.
        """
        if self.features.disable_vectorizers:
            async with conn.cursor() as cursor:
                await cursor.execute(
                    self.queries.is_vectorizer_disabled_query,
                    [self.vectorizer.id],
                )
                row = await cursor.fetchone()
                if not row:
                    raise Exception("vectorizer row not found")
                if row[0]:
                    return False

        return self._should_continue_processing_hook(loops, res)

    @tracer.wrap()
    async def _do_batch(self, conn: AsyncConnection) -> int:
        """
        Processes a batch of tasks. Fetches items from the queue, filters out
        deleted items, generates embeddings, and writes them to the database.

        Args:
            conn (AsyncConnection): The asynchronous database connection.

        Returns:
            int: The number of items processed in the batch.
        """
        processing_stats = ProcessingStats()
        start_time = time.perf_counter()
        async with conn.transaction():
            items = await self._fetch_work(conn)

            current_span = tracer.current_span()
            if current_span:
                current_span.set_tag("items_from_queue.pulled", len(items))
            await logger.adebug(f"Items pulled from queue: {len(items)}")

            # Filter out items that were deleted from the source table.
            # We use the first primary key column, since they can only
            # be null if the LEFT JOIN didn't find a match.
            items = [
                i for i in items if i[self.vectorizer.source_pk[0].attname] is not None
            ]

            if len(items) == 0:
                return 0

            num_chunks = await self._embed_and_write(conn, items)

            processing_stats.add_request_time(
                time.perf_counter() - start_time, num_chunks
            )
            await processing_stats.print_stats()

            return len(items)

    @cached_property
    def _batch_size(self) -> int:
        """Returns the batch size for processing.
        Documents take way longer to process than simple text rows,
        due to download and parsing overhead.
        So when the vectorizer is processing documents
        we use a smaller default batch size."""
        if self.vectorizer.config.processing.batch_size is not None:
            return max(1, min(self.vectorizer.config.processing.batch_size, 2048))
        else:
            if isinstance(self.vectorizer.config.loading, UriLoading):
                return 1
            else:
                return 50

    async def _fetch_work(self, conn: AsyncConnection) -> list[SourceRow]:
        """
        Fetches a batch of tasks from the work queue table. Safe for concurrent use.

        Follows the approach described in:
        https://www.timescale.com/blog/how-we-designed-a-resilient-vector-embedding-creation-system-for-postgresql-data/

        Args:
            conn (AsyncConnection): The database connection.

        Returns:
            list[SourceRow]: The rows from the source table that need to be embedded.
        """
        queue_table_oid = await self._get_queue_table_oid(conn)
        async with conn.cursor(row_factory=dict_row) as cursor:
            if self.features.loading_retries:
                await cursor.execute(
                    self.queries.fetch_work_query_with_retries,
                    (
                        self._batch_size,
                        queue_table_oid,
                    ),
                )
            else:
                await cursor.execute(
                    self.queries.fetch_work_query,
                    (
                        self._batch_size,
                        queue_table_oid,
                    ),
                )
            return await cursor.fetchall()

    async def _get_queue_table_oid(self, conn: AsyncConnection) -> int:
        """
        Retrieves the OID (Object Identifier) of the queue table.

        Args:
            conn (AsyncConnection): The database connection.

        Returns:
            int: The OID of the queue table.
        """
        if self._queue_table_oid is not None:
            return self._queue_table_oid

        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                self.queries.fetch_queue_table_oid_query,
            )
            row = await cursor.fetchone()
            if not row:
                raise Exception("work queue table doesn't exist")
            self._queue_table_oid = row["to_regclass"]
        return self._queue_table_oid

    @tracer.wrap()
    async def _embed_and_write(self, conn: AsyncConnection, items: list[SourceRow]):
        """
        Embeds the items and writes them to the database.

        - Deletes existing embeddings for the items.
        - Generates the documents to be embedded, chunks them, and formats the chunks.
        - Sends the documents to the embedding provider and writes embeddings
          to the database.
        - Logs any non-fatal errors encountered during embedding.

        Args:
            conn (AsyncConnection): The database connection.
            items (list[SourceRow]): The items to be embedded.

        Returns:
            int: The number of records written to the database.
        """

        await self._delete_embeddings(conn, items)
        count = 0
        async for records, loading_errors in self._generate_embeddings(items):
            if loading_errors:
                await self.handle_loading_retries(conn, loading_errors)
            await self._write_embeddings(conn, records)
            count += len(records)
        return count

    async def _delete_embeddings(self, conn: AsyncConnection, items: list[SourceRow]):
        """
        Deletes the embeddings for the given items from the target table.

        Args:
            conn (AsyncConnection): The database connection.
            items (list[SourceRow]): The items whose embeddings need to be deleted.
        """
        if self.vectorizer.config.destination.implementation == "column":
            return
        else:
            ids = [item[pk] for item in items for pk in self.queries.pk_attnames]
            async with conn.cursor() as cursor:
                await cursor.execute(
                    self.queries.delete_embeddings_query(
                        len(items), self.vectorizer.config.destination
                    ),
                    ids,
                )

    async def _load_copy_types(
        self, conn: AsyncConnection, destination: TableDestination
    ) -> None:
        """
        Loads the database types for the columns of the target table into
        self.copy_types.

        Args:
            conn (AsyncConnection): The database connection.
        """
        target_schema = destination.target_schema
        target_table = destination.target_table

        target_columns: list[str] = list(self.queries.pk_attnames) + [
            "chunk_seq",
            "chunk",
            "embedding",
        ]

        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                select a.attname, a.atttypid
                from pg_catalog.pg_class k
                inner join pg_catalog.pg_namespace n
                    on (k.relnamespace operator(pg_catalog.=) n.oid)
                inner join pg_catalog.pg_attribute a
                    on (k.oid operator(pg_catalog.=) a.attrelid)
                where n.nspname operator(pg_catalog.=) %s
                and k.relname operator(pg_catalog.=) %s
                AND a.attname = ANY(%s)
                and a.attnum operator(pg_catalog.>) 0
            """,
                (
                    target_schema,
                    target_table,
                    target_columns,
                ),
            )
            column_name_to_type = {row[0]: row[1] for row in await cursor.fetchall()}
            self.copy_types = [column_name_to_type[col] for col in target_columns]
        assert self.copy_types is not None
        # len(source_pk) + chunk_seq + chunk + embedding
        assert len(self.copy_types) == len(self.vectorizer.source_pk) + 3

    @tracer.wrap()
    async def _copy_embeddings(
        self,
        conn: AsyncConnection,
        records: list[EmbeddingRecord],
        destination: TableDestination,
    ):
        """
        Inserts embeddings into the target table.

        For TableDestination, uses COPY FROM STDIN WITH (FORMAT BINARY).
        For ColumnDestination, uses UPDATE statements for each row.

        Args:
            conn (AsyncConnection): The database connection.
            records (list[EmbeddingRecord]): The embedding records to be copied.
        """
        if self.copy_types is None:
            await self._load_copy_types(conn, destination)
        async with (
            conn.cursor(binary=True) as cursor,
            cursor.copy(self.queries.copy_embeddings_query(destination)) as copy,  # type: ignore
        ):
            assert self.copy_types is not None  # ugh. make pyright happy
            copy.set_types(self.copy_types)
            for record in records:
                await copy.write_row(record)

        assert self.copy_types is not None
        # len(source_pk) + chunk_seq + chunk + embedding
        assert len(self.copy_types) == len(self.vectorizer.source_pk) + 3

    async def _update_source_table(
        self,
        destination: ColumnDestination,
        conn: AsyncConnection,
        records: list[EmbeddingRecord],
    ):
        async with conn.cursor() as cursor:
            for record in records:
                pk_values = record[: len(self.queries.pk_attnames)]
                embedding = record[-1]  # Last item is the embedding
                await cursor.execute(
                    self.queries.update_embedding_query(destination),  # type: ignore
                    [embedding] + pk_values,
                )

    async def _write_embeddings(
        self, conn: AsyncConnection, records: list[EmbeddingRecord]
    ):
        if self.vectorizer.config.destination.implementation == "table":
            await self._copy_embeddings(
                conn, records, self.vectorizer.config.destination
            )

        if self.vectorizer.config.destination.implementation == "column":
            await self._update_source_table(
                self.vectorizer.config.destination, conn, records
            )

    async def _insert_vectorizer_error(
        self,
        conn: AsyncConnection,
        record: VectorizerErrorRecord,
    ):
        """
        Inserts a single vectorizer error into the errors table.

        Args:
            conn (AsyncConnection): The database connection.
            record (VectorizerErrorRecord): The error record to be inserted.
        """
        async with conn.cursor() as cursor:
            await cursor.execute(self.queries.insert_errors_query, record)

    def _get_item_pk_values(self, item: SourceRow) -> list[Any]:
        return [item[pk] for pk in self.queries.pk_attnames]

    async def _generate_embeddings(
        self, items: list[SourceRow]
    ) -> AsyncGenerator[
        tuple[list[EmbeddingRecord], list[tuple[SourceRow, LoadingError]]], None
    ]:
        """
        Generates the embeddings for the given items.

        Args:
            items (list[SourceRow]): The items to generate embeddings for.

        Returns:
            AsyncGenerator[
                tuple[
                    list[EmbeddingRecord],
                    list[tuple[SourceRow, LoadingError]],
                ], None
            ]: A tuple of embedding records and error records.
        """
        # Note: deferred import to avoid import overhead
        import numpy as np

        records_without_embeddings: list[EmbeddingRecord] = []
        loading_errors: list[tuple[SourceRow, LoadingError]] = []
        documents: list[str] = []
        for item in items:
            pk_values = self._get_item_pk_values(item)
            try:
                payload = self.vectorizer.config.loading.load(item)
            except Exception as e:
                if self.features.loading_retries:
                    loading_errors.append((item, (LoadingError(e=e))))
                continue

            payload = self.vectorizer.config.parsing.parse(item, payload)
            chunks = self.vectorizer.config.chunking.into_chunks(item, payload)
            for chunk_id, chunk in enumerate(chunks, 0):
                formatted = self.vectorizer.config.formatting.format(chunk, item)
                records_without_embeddings.append(pk_values + [chunk_id, formatted])
                documents.append(formatted)

        if loading_errors:
            yield [], loading_errors

        try:
            rwe_take = flexible_take(records_without_embeddings)
            async for embeddings in self.vectorizer.config.embedding.embed(documents):
                records: list[EmbeddingRecord] = []
                for record, embedding in zip(
                    rwe_take(len(embeddings)), embeddings, strict=True
                ):
                    records.append(record + [np.array(embedding)])
                yield records, []
        except Exception as e:
            raise EmbeddingProviderError() from e

    async def handle_loading_retries(
        self,
        conn: AsyncConnection,
        loading_errors: list[tuple[SourceRow, LoadingError]],
    ):
        for item, e in loading_errors:
            is_retryable = await self._reinsert_loading_work_to_retry(
                conn, self.vectorizer.config.loading.retries, item
            )
            await self._insert_vectorizer_error(
                conn,
                (
                    self.vectorizer.id,
                    e.msg,
                    Jsonb(
                        {
                            "loader": self.vectorizer.config.loading.implementation,  # noqa
                            "error_reason": str(e.__cause__),
                            "is_retryable": is_retryable,
                        }
                    ),
                ),
            )

    async def _reinsert_loading_work_to_retry(
        self, conn: AsyncConnection, max_loading_retries: int, item: SourceRow
    ) -> bool:
        """
        Requeue the work items that failed to generate embeddings.
        """

        loading_retries = item.get("loading_retries", 0)
        if loading_retries >= max_loading_retries:
            queue_failed_params = {
                "failure_step": "loading",
                **{
                    f"pk{i}": value
                    for i, value in enumerate(self._get_item_pk_values(item))
                },
            }

            async with conn.cursor() as cursor:
                await cursor.execute(
                    self.queries.insert_queue_failed_query, queue_failed_params
                )
            return False

        reinsert_params = {
            "loading_retries": loading_retries,
            **{
                f"pk{i}": value
                for i, value in enumerate(self._get_item_pk_values(item))
            },
        }

        async with conn.cursor() as cursor:
            await cursor.execute(
                self.queries.reinsert_work_to_retry_query,
                reinsert_params,
            )
            return True


TIKTOKEN_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "tiktoken_cache"
)
