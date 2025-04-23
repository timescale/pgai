import logging
from collections.abc import Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier

from pgai.semantic_catalog.models import Fact, ObjectDescription, SQLExample
from pgai.semantic_catalog.vectorizer import EmbeddingConfig

logger = logging.getLogger(__name__)


async def search_objects(
    con: psycopg.AsyncConnection,
    catalog_id: int,
    embedding_name: str,
    config: EmbeddingConfig,
    query: Sequence[float],
    limit: int = 5,
) -> list[ObjectDescription]:
    logger.debug(f"searching semantic catalog {catalog_id}")
    async with con.cursor(row_factory=dict_row) as cur:
        sql = SQL("""\
            select x.*
            from ai.{table} x
            order by x.{column} <=> %s::vector({dimensions})
            limit %s
        """).format(
            table=Identifier(f"semantic_catalog_obj_{catalog_id}"),
            dimensions=SQL(str(int(config.dimensions))),  # pyright: ignore [reportArgumentType]
            column=Identifier(embedding_name),
        )
        await cur.execute(sql, (query, limit))
        results: list[ObjectDescription] = []
        for row in await cur.fetchall():
            results.append(ObjectDescription(**row))
        logger.debug(f"found {len(results)} objects")
        return results


async def search_sql_examples(
    con: psycopg.AsyncConnection,
    catalog_id: int,
    embedding_name: str,
    config: EmbeddingConfig,
    query: Sequence[float],
    limit: int = 5,
) -> list[SQLExample]:
    logger.debug(f"searching semantic catalog {catalog_id}")
    async with con.cursor(row_factory=dict_row) as cur:
        sql = SQL("""\
            select x.*
            from ai.{table} x
            order by x.{column} <=> %s::vector({dimensions})
            limit %s
        """).format(
            table=Identifier(f"semantic_catalog_sql_{catalog_id}"),
            dimensions=SQL(str(int(config.dimensions))),  # pyright: ignore [reportArgumentType]
            column=Identifier(embedding_name),
        )
        await cur.execute(sql, (query, limit))
        results: list[SQLExample] = []
        for row in await cur.fetchall():
            results.append(SQLExample(**row))
        logger.debug(f"found {len(results)} examples")
        return results


async def search_facts(
    con: psycopg.AsyncConnection,
    catalog_id: int,
    embedding_name: str,
    config: EmbeddingConfig,
    query: Sequence[float],
    limit: int = 5,
) -> list[Fact]:
    logger.debug(f"searching semantic catalog {catalog_id}")
    async with con.cursor(row_factory=dict_row) as cur:
        sql = SQL("""\
            select x.*
            from ai.{table} x
            order by x.{column} <=> %s::vector({dimensions})
            limit %s
        """).format(
            table=Identifier(f"semantic_catalog_fact_{catalog_id}"),
            dimensions=SQL(str(int(config.dimensions))),  # pyright: ignore [reportArgumentType]
            column=Identifier(embedding_name),
        )
        await cur.execute(sql, (query, limit))
        results: list[Fact] = []
        for row in await cur.fetchall():
            results.append(Fact(**row))
        logger.debug(f"found {len(results)} facts")
        return results
