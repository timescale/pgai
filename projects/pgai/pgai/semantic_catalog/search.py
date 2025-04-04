from collections.abc import Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier

from pgai.semantic_catalog.models import Fact, ObjectDescription, SQLExample
from pgai.semantic_catalog.vectorizer import EmbeddingConfig, vectorize_query


async def search_objects(
    con: psycopg.AsyncConnection,
    id: int,
    name: str,
    config: EmbeddingConfig,
    query: str,
    limit: int = 5,
) -> list[ObjectDescription]:
    v: Sequence[float] = await vectorize_query(config, query)
    async with con.cursor(row_factory=dict_row) as cur:
        sql = SQL("""\
            select x.*
            from ai.{table} x
            order by x.{column} <=> %s::vector({dimensions})
            limit %s
        """).format(
            table=Identifier(f"semantic_catalog_obj_{id}"),
            dimensions=SQL(str(int(config.dimensions))),  # pyright: ignore [reportArgumentType]
            column=Identifier(name),
        )
        await cur.execute(sql, (v, limit))
        results: list[ObjectDescription] = []
        for row in await cur.fetchall():
            results.append(ObjectDescription(**row))
        return results


async def search_sql_examples(
    con: psycopg.AsyncConnection,
    id: int,
    name: str,
    config: EmbeddingConfig,
    query: str,
    limit: int = 5,
) -> list[SQLExample]:
    v: Sequence[float] = await vectorize_query(config, query)
    async with con.cursor(row_factory=dict_row) as cur:
        sql = SQL("""\
            select x.*
            from ai.{table} x
            order by x.{column} <=> %s::vector({dimensions})
            limit %s
        """).format(
            table=Identifier(f"semantic_catalog_sql_{id}"),
            dimensions=SQL(str(int(config.dimensions))),  # pyright: ignore [reportArgumentType]
            column=Identifier(name),
        )
        await cur.execute(sql, (v, limit))
        results: list[SQLExample] = []
        for row in await cur.fetchall():
            results.append(SQLExample(**row))
        return results


async def search_facts(
    con: psycopg.AsyncConnection,
    id: int,
    name: str,
    config: EmbeddingConfig,
    query: str,
    limit: int = 5,
) -> list[Fact]:
    v: Sequence[float] = await vectorize_query(config, query)
    async with con.cursor(row_factory=dict_row) as cur:
        sql = SQL("""\
            select x.*
            from ai.{table} x
            order by x.{column} <=> %s::vector({dimensions})
            limit %s
        """).format(
            table=Identifier(f"semantic_catalog_fact_{id}"),
            dimensions=SQL(str(int(config.dimensions))),  # pyright: ignore [reportArgumentType]
            column=Identifier(name),
        )
        await cur.execute(sql, (v, limit))
        results: list[Fact] = []
        for row in await cur.fetchall():
            results.append(Fact(**row))
        return results
