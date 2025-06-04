import logging
from collections.abc import Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier, Literal

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
    exclude_ids: Sequence[int] | None = None,
) -> list[ObjectDescription]:
    """Search for database objects in the semantic catalog using vector similarity.

    Performs a semantic search for database objects (tables, views, functions, etc.)
    using vector similarity between the query embedding and object embeddings.

    Args:
        con: Asynchronous database connection to the catalog database.
        catalog_id: ID of the semantic catalog to search in.
        embedding_name: Name of the embedding column to search in.
        config: Configuration for the embedding model used.
        query: Query vector (embedding) to compare against stored object embeddings.
        limit: Maximum number of results to return (default: 5).
        exclude_ids: ids of objects to exclude from search results

    Returns:
        A list of ObjectDescription objects ordered by similarity to the query vector.
    """
    logger.debug(f"searching semantic catalog {catalog_id}")
    params = dict(query=query, limit=limit)
    if exclude_ids:
        params["exclude_ids"] = exclude_ids
    async with con.cursor(row_factory=dict_row) as cur:
        sql = SQL("""\
            select x.*
            from ai.{table} x
            {filter}
            order by x.{column} <=> %(query)s::vector({dimensions})
            limit %(limit)s
        """).format(
            table=Identifier(f"semantic_catalog_obj_{catalog_id}"),
            dimensions=Literal(config.dimensions),
            column=Identifier(embedding_name),
            filter=SQL("")
            if not exclude_ids
            else SQL("where id != any(%(exclude_ids)s)"),
        )
        await cur.execute(sql, params)
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
    exclude_ids: Sequence[int] | None = None,
) -> list[SQLExample]:
    """Search for SQL examples in the semantic catalog using vector similarity.

    Performs a semantic search for SQL examples using vector similarity between
    the query embedding and SQL example embeddings.

    Args:
        con: Asynchronous database connection to the catalog database.
        catalog_id: ID of the semantic catalog to search in.
        embedding_name: Name of the embedding column to search in.
        config: Configuration for the embedding model used.
        query: Query vector (embedding) to compare against stored SQL example embeddings.
        limit: Maximum number of results to return (default: 5).
        exclude_ids: ids of sql examples to exclude from search results

    Returns:
        A list of SQLExample objects ordered by similarity to the query vector.
    """  # noqa: E501
    logger.debug(f"searching semantic catalog {catalog_id}")
    params = dict(query=query, limit=limit)
    if exclude_ids:
        params["exclude_ids"] = exclude_ids
    async with con.cursor(row_factory=dict_row) as cur:
        sql = SQL("""\
            select x.*
            from ai.{table} x
            {filter}
            order by x.{column} <=> %(query)s::vector({dimensions})
            limit %(limit)s
        """).format(
            table=Identifier(f"semantic_catalog_sql_{catalog_id}"),
            dimensions=Literal(config.dimensions),
            column=Identifier(embedding_name),
            filter=SQL("")
            if not exclude_ids
            else SQL("where id != any(%(exclude_ids)s)"),
        )
        await cur.execute(sql, params)
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
    exclude_ids: Sequence[int] | None = None,
) -> list[Fact]:
    """Search for facts in the semantic catalog using vector similarity.

    Performs a semantic search for facts using vector similarity between
    the query embedding and fact embeddings.

    Args:
        con: Asynchronous database connection to the catalog database.
        catalog_id: ID of the semantic catalog to search in.
        embedding_name: Name of the embedding column to search in.
        config: Configuration for the embedding model used.
        query: Query vector (embedding) to compare against stored fact embeddings.
        limit: Maximum number of results to return (default: 5).
        exclude_ids: ids of facts to exclude from search results

    Returns:
        A list of Fact objects ordered by similarity to the query vector.
    """
    logger.debug(f"searching semantic catalog {catalog_id}")
    params = dict(query=query, limit=limit)
    if exclude_ids:
        params["exclude_ids"] = exclude_ids
    async with con.cursor(row_factory=dict_row) as cur:
        sql = SQL("""\
            select x.*
            from ai.{table} x
            {filter}
            order by x.{column} <=> %(query)s::vector({dimensions})
            limit %(limit)s
        """).format(
            table=Identifier(f"semantic_catalog_fact_{catalog_id}"),
            dimensions=Literal(config.dimensions),
            column=Identifier(embedding_name),
            filter=SQL("")
            if not exclude_ids
            else SQL("where id != any(%(exclude_ids)s)"),
        )
        await cur.execute(sql, params)
        results: list[Fact] = []
        for row in await cur.fetchall():
            results.append(Fact(**row))
        logger.debug(f"found {len(results)} facts")
        return results
