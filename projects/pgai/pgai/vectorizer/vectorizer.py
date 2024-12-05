import asyncio
import json
import os
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from functools import cached_property
from itertools import repeat
from typing import Any, TypeAlias, Dict

import numpy as np
import psycopg
import structlog
from ddtrace import tracer
from pgvector.psycopg import register_vector_async  # type: ignore
from psycopg import AsyncConnection, sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic.dataclasses import dataclass
from pydantic.fields import Field
import openai

from .chunking import (
    LangChainCharacterTextSplitter,
    LangChainRecursiveCharacterTextSplitter,
)
from .embeddings import ChunkEmbeddingError, Ollama, OpenAI, VoyageAI
from .formatting import ChunkValue, PythonTemplate
from .processing import ProcessingDefault

logger = structlog.get_logger()

VectorizerErrorRecord: TypeAlias = tuple[int, str, Jsonb]
EmbeddingRecord: TypeAlias = list[Any]
SourceRow: TypeAlias = dict[str, Any]

DEFAULT_CONCURRENCY = 1

VECTORIZER_FAILED = "vectorizer failed with unexpected error"


class EmbeddingProviderError(Exception):
    """
    Raised when an embedding provider API request fails.
    """

    msg = "embedding provider failed"


@dataclass
class PkAtt:
    """
    Represents an attribute of a primary key.

    Attributes:
        attname (str): The name of the attribute (column).
        typname (str): The type of the attribute.
    """

    attname: str
    typname: str


@dataclass
class Config:
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
    embedding: OpenAI | Ollama | VoyageAI
    processing: ProcessingDefault
    chunking: (
        LangChainCharacterTextSplitter | LangChainRecursiveCharacterTextSplitter
    ) = Field(..., discriminator="implementation")
    formatting: PythonTemplate | ChunkValue = Field(..., discriminator="implementation")


@dataclass
class Vectorizer:
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
            Default is "vectorizer_errors".
    """

    id: int
    config: Config
    queue_table: str
    queue_schema: str
    source_schema: str
    source_table: str
    target_schema: str
    target_table: str
    source_pk: list[PkAtt]
    errors_schema: str = "ai"
    errors_table: str = "vectorizer_errors"


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
        represents the SQL expression "author, title".
        """
        return sql.SQL(" ,").join(
            [sql.Identifier(a.attname) for a in self.vectorizer.source_pk]
        )

    @cached_property
    def pk_attnames(self) -> list[str]:
        """
        Returns a list of primary key attribute names. For example, if the
        primary key has 2 fields (author, title), it will return ["author", "title"].
        """
        return [a.attname for a in self.vectorizer.source_pk]

    @property
    def pk_fields(self) -> list[sql.Identifier]:
        """
        Returns the SQL identifiers for primary key fields.
        """
        return [sql.Identifier(a.attname) for a in self.vectorizer.source_pk]

    @property
    def target_table_ident(self) -> sql.Identifier:
        """
        Returns the SQL identifier for the fully qualified name of the target table.
        """

        return sql.Identifier(
            self.vectorizer.target_schema, self.vectorizer.target_table
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
                    WHERE locked = true
                    AND {delete_join_predicates}
                )
                SELECT {source_table}.*
                FROM locked_items
                LEFT JOIN {source_schema}.{source_table} USING ({pk_fields})
                WHERE locked = true
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
        )

    @cached_property
    def fetch_queue_table_oid_query(self) -> sql.Composed:
        return sql.SQL("SELECT to_regclass('{}')::oid").format(
            sql.Identifier(self.vectorizer.queue_schema, self.vectorizer.queue_table)
        )

    def delete_embeddings_query(self, items_count: int) -> sql.Composed:
        return sql.SQL("DELETE FROM {} WHERE ({}) IN ({})").format(
            self.target_table_ident,
            self.pk_fields_sql,
            self._pks_placeholders_tuples(items_count),
        )

    @cached_property
    def copy_types(self) -> list[str]:
        types = [a.typname for a in self.vectorizer.source_pk]
        types.extend(["int4", "text", "vector"])
        return types

    @cached_property
    def copy_embeddings_query(self) -> sql.Composed:
        return sql.SQL(
            "COPY {} ({}, chunk_seq, chunk, embedding) FROM STDIN WITH (FORMAT BINARY)"
        ).format(
            self.target_table_ident,
            self.pk_fields_sql,
        )

    @cached_property
    def insert_embeddings_query(self) -> sql.Composed:
        return sql.SQL(
            "INSERT INTO {} ({}, chunk_seq, chunk, embedding) VALUES ({}, %s, %s, %s)"
        ).format(
            self.target_table_ident,
            self.pk_fields_sql,
            sql.SQL(" ,").join(list(repeat(sql.SQL("%s"), len(self.pk_fields)))),
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


class Worker:
    """
    Responsible for processing items from the work queue and generating embeddings.

    The Worker fetches tasks from a database queue table, processes them using
    the vectorizer, and writes the resulting embeddings or errors back to the
    database.

    Attributes:
        db_url (str): The URL of the database to connect to.
        vectorizer (Vectorizer): The vectorizer configuration used for processing.
        queries (VectorizerQueryBuilder): A query builder instance used for
            generating SQL queries.
    """

    _queue_table_oid = None
    _continue_processing: Callable[[int, int], bool]

    def __init__(
        self,
        db_url: str,
        vectorizer: Vectorizer,
        continue_processing: None | Callable[[int, int], bool] = None,
    ):
        self.db_url = db_url
        self.vectorizer = vectorizer
        self.queries = VectorizerQueryBuilder(vectorizer)
        self._continue_processing = continue_processing or (lambda _loops, _res: True)

    async def run(self) -> int:
        """
        Embedding loop. Continuously fetches tasks from the work queue and
        processes them within the context of a transaction.

        Returns:
            int: The number of tasks processed from the work queue.
        """
        res = 0
        loops = 0

        async with await psycopg.AsyncConnection.connect(self.db_url) as conn:
            await register_vector_async(conn)
            await self.vectorizer.config.embedding.setup()
            while True:
                if not self._continue_processing(loops, res):
                    await self._check_and_process_openai_batches(conn)
                    # TODO how can we run this only after hitting the rate limit of the normal openai batch embedding api?
                    await self._do_openai_batch(conn)
                    return res
                items_processed = await self._do_batch(conn)
                if items_processed == 0:
                    return res
                res += items_processed
                loops += 1

    async def _create_batch_table(self, conn: AsyncConnection):
        # TODO this does not feel like the way to go, is there a way to do these kind of migrations properly?
        await conn.execute("""
CREATE TABLE IF NOT EXISTS ai.embedding_batches
(
    openai_batch_id VARCHAR(255) PRIMARY KEY,
    input_file_id   VARCHAR(255) NOT NULL,
    output_file_id  VARCHAR(255),
    status          VARCHAR(255) NOT NULL,
    errors          JSONB,
    created_at      TIMESTAMP(0) NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMP(0),
    completed_at    TIMESTAMP(0),
    failed_at       TIMESTAMP(0)
);
                """)
        await conn.execute("""
                CREATE INDEX IF NOT EXISTS embedding_batches_status_index ON ai.embedding_batches (status);
                """)
        return await conn.execute("""
CREATE TABLE IF NOT EXISTS ai.embedding_batch_chunks
(
    id                 VARCHAR(255) PRIMARY KEY,
    embedding_batch_id VARCHAR(255) REFERENCES ai.embedding_batches (openai_batch_id),
    text               TEXT
);
        """)

    @tracer.wrap()
    async def _do_openai_batch(self, conn: AsyncConnection) -> int:
        """
        Creates embeddings using openai's batch processing api. This allows to process
        very large amounts of data faster than with the embeddings api, because the
        batch api has vastly higher rate limits.

        Args:
            conn (AsyncConnection): The asynchronous database connection.
        """

        # TODO do nothing when openai is not configured

        try:
            async with conn.transaction():
                items = await self._fetch_work(conn)

                await logger.adebug(f"Items pulled from queue for openai batch embedding: {len(items)}")

                # Filter out items that were deleted from the source table.
                # We use the first primary key column, since they can only
                # be null if the LEFT JOIN didn't find a match.
                items = [
                    i
                    for i in items
                    if i[self.vectorizer.source_pk[0].attname] is not None
                ]

                if len(items) == 0:
                    return 0

                created_batch, documents = await self._generate_embedding_batch(items)

                await conn.execute("""
                INSERT INTO ai.embedding_batches (
                    openai_batch_id,
                    input_file_id,
                    output_file_id,
                    status,
                    errors,
                    expires_at
                ) VALUES (
                    %(openai_batch_id)s,
                    %(input_file_id)s,
                    %(output_file_id)s,
                    %(status)s,
                    %(errors)s,
                    %(expires_at)s
                )
                """, {
                    'openai_batch_id': created_batch.id,
                    'input_file_id': created_batch.input_file_id,
                    'output_file_id': created_batch.output_file_id,
                    'status': created_batch.status,
                    'errors': created_batch.errors,
                    'expires_at': datetime.fromtimestamp(created_batch.expires_at, timezone.utc),
                })

                for doc in documents:
                    await conn.execute("""
                    INSERT INTO ai.embedding_batch_chunks (
                        id,
                        embedding_batch_id,
                        text
                    ) VALUES (
                        %(id)s,
                        %(embedding_batch_id)s,
                        %(text)s
                    )
                    """, {
                        'id': doc['unique_full_chunk_id'],
                        'embedding_batch_id': created_batch.id,
                        'text': doc['chunk']
                    })

                # TODO how to delete submitted entries from the queue?

                return len(items)
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

    @tracer.wrap()
    async def _check_and_process_openai_batches(self, conn: AsyncConnection):
        async with (
            conn.transaction(),
            conn.cursor() as cursor,
        ):
            client = OpenAI() # TODO how can I get the client? There has to be one created already that I can use?
            await conn.execute("SELECT openai_batch_id, output_file_id FROM embedding_batches WHERE status not in('failed', 'processed', 'prepared')")
            for batch_row in cursor.fetchall():
                batch = client.batches.retrieve(batch_row['openai_batch_id'])

                await conn.execute("""
                    UPDATE embedding_batches 
                    SET status = %s, completed_at = %s, failed_at = %s, 
                        output_file_id = %s, errors = %s 
                    WHERE id = %s
                """, (
                    batch['status'],
                    batch.get('completed_at'),
                    batch.get('failed_at'),
                    batch.get('output_file_id'),
                    Jsonb(batch.get('errors')),
                    batch_row['openai_batch_id'],
                ))

                # batch has been processed successfully in openai, that means we can
                # collect the results and store them in the database.
                if batch['status'] == "completed":
                    await self._embed_and_write_from_batch(conn, batch, client)

                    await cursor.execute("""
                        UPDATE embedding_batches 
                        SET status = %s 
                        WHERE id = %s
                    """, (
                        "processed",
                        batch_row['openai_batch_id'],
                    ))

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
        try:
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
                    i
                    for i in items
                    if i[self.vectorizer.source_pk[0].attname] is not None
                ]

                if len(items) == 0:
                    return 0

                num_chunks = await self._embed_and_write(conn, items)

                processing_stats.add_request_time(
                    time.perf_counter() - start_time, num_chunks
                )
                await processing_stats.print_stats()

                return len(items)
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
            # This is to make the traceback not as verbose by removing
            # the lines about our wrapper exception being casused by
            # the actual exception.
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
            await cursor.execute(
                self.queries.fetch_work_query,
                (
                    self.vectorizer.config.processing.batch_size,
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
        records, errors = await self._generate_embeddings(items)
        # await self._insert_embeddings(conn, records)
        await self._copy_embeddings(conn, records)
        if errors:
            await self._insert_vectorizer_errors(conn, errors)

        return len(records)

    @tracer.wrap()
    async def _embed_and_write_from_batch(
            self,
            conn: AsyncConnection,
            batch: openai.types.Batch,
            client: OpenAI,
    ):
        """
        Embeds the items and writes them to the database.

        - Deletes existing embeddings for the items.
        - Generates the documents to be embedded, chunks them, and formats the chunks.
        - Sends the documents to the embedding provider and writes embeddings
          to the database.
        - Logs any non-fatal errors encountered during embedding.

        Args:
            conn (AsyncConnection): The database connection.
            batch: The batch as retrieved from OpenAI's api.
            client: The OpenAI client to use.

        Returns:
            int: The number of records written to the database.
        """
        batch_file = client.files.content(batch.output_file_id)

        batch_data = batch_file.text.strip().split('\n')
        num_records = 0
        document_chunks: Dict[int, Dict[int, str]] = {} # outer key is the document id, inner key is the chunk id, content is the chunk
        all_items = []
        records: list[EmbeddingRecord] = []
        for line in batch_data:
            json_line = json.loads(line)
            if "custom_id" in json_line and "response" in json_line:

                custom_id = json_line['custom_id']
                pk, document_id, chunk_seq = custom_id.split('_')
                embedding_data = json_line['response']['body']['data']

                item = {pk: document_id}
                all_items.append(item)

                if document_id not in document_chunks:
                    document_chunks[document_id] = {}
                    chunks = self.vectorizer.config.chunking.into_chunks(item)

                    for chunk_id, chunk in enumerate(chunks, 0):
                        formatted = self.vectorizer.config.formatting.format(chunk, item)
                        document_chunks[document_id][chunk_id] = formatted

                records.append(pk + [chunk_seq, document_chunks[document_id][chunk_seq]] + [np.array(embedding_data)])

        await self._delete_embeddings(conn, all_items)
        await self._copy_embeddings(conn, records)

        return num_records

    async def _delete_embeddings(self, conn: AsyncConnection, items: list[SourceRow]):
        """
        Deletes the embeddings for the given items from the target table.

        Args:
            conn (AsyncConnection): The database connection.
            items (list[SourceRow]): The items whose embeddings need to be deleted.
        """
        ids = [item[pk] for item in items for pk in self.queries.pk_attnames]
        async with conn.cursor() as cursor:
            await cursor.execute(self.queries.delete_embeddings_query(len(items)), ids)

    @tracer.wrap()
    async def _copy_embeddings(
        self,
        conn: AsyncConnection,
        records: list[EmbeddingRecord],
    ):
        """
        Inserts embeddings into the embedding table using COPY FROM STDIN WITH
        (FORMAT BINARY).

        Args:
            conn (AsyncConnection): The database connection.
            records (list[EmbeddingRecord]): The embedding records to be copied.
        """
        async with (
            conn.cursor(binary=True) as cursor,
            cursor.copy(self.queries.copy_embeddings_query) as copy,
        ):
            copy.set_types(self.queries.copy_types)
            for record in records:
                await copy.write_row(record)

    async def _insert_vectorizer_errors(
        self,
        conn: AsyncConnection,
        records: list[VectorizerErrorRecord],
    ):
        """
        Inserts vectorizer errors into the errors table.

        Args:
            conn (AsyncConnection): The database connection.
            records (list[VectorizerErrorRecord]): The error records to be inserted.
        """
        async with conn.cursor() as cursor:
            await cursor.executemany(self.queries.insert_errors_query, records)

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
    ) -> tuple[list[EmbeddingRecord], list[VectorizerErrorRecord]]:
        """
        Generates the embeddings for the given items.

        Args:
            items (list[SourceRow]): The items to generate embeddings for.

        Returns:
            tuple[list[EmbeddingRecord], list[VectorizerErrorRecord]]: A tuple
                of embedding records and error records.
        """
        records_without_embeddings: list[EmbeddingRecord] = []
        documents: list[str] = []
        for item in items:
            pk = self._get_item_pk_values(item)
            chunks = self.vectorizer.config.chunking.into_chunks(item)
            for chunk_id, chunk in enumerate(chunks, 0):
                formatted = self.vectorizer.config.formatting.format(chunk, item)
                records_without_embeddings.append(pk + [chunk_id, formatted])
                documents.append(formatted)

        try:
            embeddings = await self.vectorizer.config.embedding.embed(documents)
        except Exception as e:
            raise EmbeddingProviderError() from e

        assert len(embeddings) == len(records_without_embeddings)

        records: list[EmbeddingRecord] = []
        errors: list[VectorizerErrorRecord] = []
        for record, embedding in zip(
            records_without_embeddings, embeddings, strict=True
        ):
            if isinstance(embedding, ChunkEmbeddingError):
                errors.append(self._vectorizer_error_record(record, embedding))
            else:
                records.append(record + [np.array(embedding)])
        return records, errors

    async def _generate_embedding_batch(
        self, items: list[SourceRow]
    ) -> openai.types.Batch:
        documents: list[dict[str, Any]] = []
        for item in items:
            pk = self._get_item_pk_values(item)
            chunks = self.vectorizer.config.chunking.into_chunks(item)
            for chunk_id, chunk in enumerate(chunks, 0):
                formatted = self.vectorizer.config.formatting.format(chunk, item)
                unique_full_chunk_id = [
                    ','.join(self.queries.pk_attnames),
                    ','.join(map(str, pk)),
                    str(chunk_id),
                ]
                documents.append({
                    'unique_full_chunk_id': ':::'.join(unique_full_chunk_id),
                    'chunk': formatted,
                })

        try:
            return await self.vectorizer.config.embedding.create_and_submit_embedding_batch(documents)
        except Exception as e:
            raise EmbeddingProviderError() from e

    def _vectorizer_error_record(
        self, record: EmbeddingRecord, chunk_error: ChunkEmbeddingError
    ) -> VectorizerErrorRecord:
        return (
            self.vectorizer.id,
            chunk_error.error,
            Jsonb(
                {
                    "pk": {
                        pk_attname: record[i]
                        for i, pk_attname in enumerate(self.queries.pk_attnames)
                    },
                    "chunk_id": record[-2],
                    "chunk": record[-1],
                    "error_reason": chunk_error.error_details,
                }
            ),
        )


TIKTOKEN_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "tiktoken_cache"
)
