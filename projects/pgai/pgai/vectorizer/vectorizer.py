import asyncio
import threading
import time
from functools import cached_property
from itertools import repeat
from typing import Any, TypeAlias

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

from .chunking import (
    LangChainCharacterTextSplitter,
    LangChainRecursiveCharacterTextSplitter,
)
from .embeddings import ChunkEmbeddingError, OpenAI
from .formatting import ChunkValue, PythonTemplate
from .processing import ProcessingDefault

logger = structlog.get_logger()

VectorizerErrorRecord: TypeAlias = tuple[int, str, Jsonb]
EmbeddingRecord: TypeAlias = list[Any]
SourceRow: TypeAlias = dict[str, Any]

DEFAULT_CONCURRENCY = 1

VECTORIZER_FAILED = "vectorizer failed with unexpected error"


class EmbeddingProviderError(Exception):
    msg = "embedding provider failed"


@dataclass
class PkAtt:
    attname: str
    typname: str


@dataclass
class Config:
    version: str
    embedding: OpenAI
    processing: ProcessingDefault
    chunking: (
        LangChainCharacterTextSplitter | LangChainRecursiveCharacterTextSplitter
    ) = Field(..., discriminator="implementation")
    formatting: PythonTemplate | ChunkValue = Field(..., discriminator="implementation")


@dataclass
class Vectorizer:
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
    def __init__(self, vectorizer: Vectorizer):
        self.vectorizer = vectorizer

    @property
    def pk_fields_sql(self) -> sql.Composed:
        return sql.SQL(" ,").join(
            [sql.Identifier(a.attname) for a in self.vectorizer.source_pk]
        )

    @cached_property
    def pk_attnames(self) -> list[str]:
        return [a.attname for a in self.vectorizer.source_pk]

    @property
    def pk_fields(self) -> list[sql.Identifier]:
        return [sql.Identifier(a.attname) for a in self.vectorizer.source_pk]

    @property
    def target_table_ident(self) -> sql.Identifier:
        return sql.Identifier(
            self.vectorizer.target_schema, self.vectorizer.target_table
        )

    @property
    def errors_table_ident(self) -> sql.Identifier:
        return sql.Identifier(
            self.vectorizer.errors_schema, self.vectorizer.errors_table
        )

    @property
    def queue_table_ident(self) -> sql.Identifier:
        return sql.Identifier(self.vectorizer.queue_schema, self.vectorizer.queue_table)

    @cached_property
    def fetch_work_query(self) -> sql.Composed:
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
        self.total_processing_time += duration
        self.total_chunks += chunk_count

    async def print_stats(self):
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
    _queue_table_oid = None

    def __init__(self, db_url: str, vectorizer: Vectorizer):
        self.db_url = db_url
        self.vectorizer = vectorizer
        self.queries = VectorizerQueryBuilder(vectorizer)

    async def run(self) -> int:
        """Embedding loop. Fetches tasks from the work queue, processes them in the
        context of a transaction.

        Returns:
            The number of tasks processed from the work queue.
        """
        res = 0

        async with await psycopg.AsyncConnection.connect(self.db_url) as conn:
            await register_vector_async(conn)
            while True:
                items_processed = await self._do_batch(conn)
                if items_processed == 0:
                    return res
                res += items_processed

    @tracer.wrap()
    async def _do_batch(self, conn: AsyncConnection) -> int:
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
        """Fetches a batch of tasks from the work queue table. It's safe for
        concurrent use.

        Follows the approach described in:

        https://www.timescale.com/blog/how-we-designed-a-resilient-vector-embedding-creation-system-for-postgresql-data/

        Args:
            conn: connection to the database.

        Returns:
            The rows from the source table that need to be embedded.
        """
        queue_table_oid = await self._get_queue_table_oid(conn)
        async with conn.cursor(row_factory=dict_row) as cursor:
            # TODO: What if the transaction is rolled back? Are we going to keep
            # processing the same task over an over. Do we abort? Move the work
            # tasks to a dead letter queue ? Retry many times?
            await cursor.execute(
                self.queries.fetch_work_query,
                (
                    self.vectorizer.config.processing.batch_size,
                    queue_table_oid,
                ),
            )
            return await cursor.fetchall()

    async def _get_queue_table_oid(self, conn: AsyncConnection) -> int:
        if self._queue_table_oid is not None:
            return self._queue_table_oid

        async with conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                self.queries.fetch_queue_table_oid_query,
            )
            row = await cursor.fetchone()
            if not row:
                # TODO: if the work queue table doesn't exists how do we handle it?
                # We should have a specific code for errors of this kind. Tables
                # not existing, columns not existing, etc.
                raise Exception("work queue table doesn't exist")
            self._queue_table_oid = row["to_regclass"]
        return self._queue_table_oid

    @tracer.wrap()
    async def _embed_and_write(self, conn: AsyncConnection, items: list[SourceRow]):
        """Embeds the items and writes them to the database:

        - Deletes items from the embdedding table that are going to be updated.
        - Generates the documents to embedded. Generates the chunks from the
          source column, and formats the chunks based on the formatting
          configuration.
        - Sends the documents to the embeddings provider to generate the
          embeddings.
        - Writes the embeddings to the database.
        - Write any non-fatal errors, like individual chunks that couldn't be
          embed.
        """

        await self._delete_embeddings(conn, items)
        records, errors = await self._generate_embeddings(items)
        # await self._insert_embeddings(conn, records)
        await self._copy_embeddings(conn, records)
        if errors:
            await self._insert_vectorizer_errors(conn, errors)

        return len(records)

    async def _delete_embeddings(self, conn: AsyncConnection, items: list[SourceRow]):
        """Deletes the embeddings for the given item."""
        ids = [item[pk] for item in items for pk in self.queries.pk_attnames]
        async with conn.cursor() as cursor:
            await cursor.execute(self.queries.delete_embeddings_query(len(items)), ids)

    @tracer.wrap()
    async def _insert_embeddings(
        self,
        conn: AsyncConnection,
        records: list[EmbeddingRecord],
    ):
        """Inserts embeddings into the embedding table"""
        async with conn.cursor() as cursor:
            await cursor.executemany(self.queries.insert_embeddings_query, records)

    @tracer.wrap()
    async def _copy_embeddings(
        self,
        conn: AsyncConnection,
        records: list[EmbeddingRecord],
    ):
        """Inserts embeddings into the embedding table using
        COPY FROM STDIN WITH (FORMAT BINARY)"""
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
        """Inserts vectorizer errors into the errors table"""
        async with conn.cursor() as cursor:
            await cursor.executemany(self.queries.insert_errors_query, records)

    async def _insert_vectorizer_error(
        self,
        conn: AsyncConnection,
        record: VectorizerErrorRecord,
    ):
        """Inserts a vectorizer error into the errors table"""
        async with conn.cursor() as cursor:
            await cursor.execute(self.queries.insert_errors_query, record)

    def _get_item_pk_values(self, item: SourceRow) -> list[Any]:
        return [item[pk] for pk in self.queries.pk_attnames]

    async def _generate_embeddings(
        self, items: list[SourceRow]
    ) -> tuple[list[EmbeddingRecord], list[VectorizerErrorRecord]]:
        """Generates the embeddings for the items."""
        records_without_embeddings: list[EmbeddingRecord] = []
        documents: list[str] = []
        for item in items:
            pk = self._get_item_pk_values(item)
            chunks = self.vectorizer.config.chunking.into_chunks(item)
            records_without_embeddings.extend(
                [pk + [chunk_id, chunk] for chunk_id, chunk in enumerate(chunks, 1)]
            )
            documents.extend(
                [
                    self.vectorizer.config.formatting.format(chunk, item)
                    for chunk in chunks
                ]
            )

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
