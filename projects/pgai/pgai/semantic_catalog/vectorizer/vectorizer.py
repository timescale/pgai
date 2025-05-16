"""Core vectorizer functionality for the semantic catalog.

This module provides the core functionality for vectorizing content in the semantic catalog.
It includes configuration models for different embedding providers, functions for retrieving
content to be vectorized, and functions for processing and saving embeddings.

The vectorizer supports multiple embedding providers (SentenceTransformers, Ollama, OpenAI)
and can vectorize different types of content (database objects, SQL examples, facts).
"""  # noqa: E501

import logging
from collections.abc import Sequence
from typing import Any, Literal

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier
from pydantic import BaseModel

from pgai.semantic_catalog.vectorizer.models import EmbedRow

logger = logging.getLogger(__name__)


class SentenceTransformersConfig(BaseModel):
    """Configuration for SentenceTransformers embedding model.

    This class defines the configuration parameters for using SentenceTransformers
    as an embedding provider in the semantic catalog.

    Attributes:
        implementation: The implementation type, always "sentence_transformers".
        config_type: The configuration type, always "embedding".
        model: The name of the SentenceTransformers model to use.
        dimensions: The number of dimensions in the resulting embeddings.
    """

    implementation: Literal["sentence_transformers"] = "sentence_transformers"
    config_type: Literal["embedding"] = "embedding"
    model: str
    dimensions: int

    @classmethod
    def create(cls, model: str, dimensions: int):
        """Create a new SentenceTransformersConfig instance.

        Args:
            model: The name of the SentenceTransformers model to use.
            dimensions: The number of dimensions in the resulting embeddings.

        Returns:
            A new SentenceTransformersConfig instance.
        """
        return cls(
            implementation="sentence_transformers",
            config_type="embedding",
            model=model,
            dimensions=dimensions,
        )


class OllamaConfig(BaseModel):
    """Configuration for Ollama embedding model.

    This class defines the configuration parameters for using Ollama
    as an embedding provider in the semantic catalog.

    Attributes:
        implementation: The implementation type, always "ollama".
        config_type: The configuration type, always "embedding".
        model: The name of the Ollama model to use.
        dimensions: The number of dimensions in the resulting embeddings.
        base_url: Optional base URL for the Ollama API server.
    """

    implementation: Literal["ollama"] = "ollama"
    config_type: Literal["embedding"] = "embedding"
    model: str
    dimensions: int
    base_url: str | None = None

    @classmethod
    def create(cls, model: str, dimensions: int, base_url: str | None = None):
        """Create a new OllamaConfig instance.

        Args:
            model: The name of the Ollama model to use.
            dimensions: The number of dimensions in the resulting embeddings.
            base_url: Optional base URL for the Ollama API server.

        Returns:
            A new OllamaConfig instance.
        """
        return cls(
            implementation="ollama",
            config_type="embedding",
            model=model,
            dimensions=dimensions,
            base_url=base_url,
        )


class OpenAIConfig(BaseModel):
    """Configuration for OpenAI embedding model.

    This class defines the configuration parameters for using OpenAI
    as an embedding provider in the semantic catalog.

    Attributes:
        implementation: The implementation type, always "openai".
        config_type: The configuration type, always "embedding".
        model: The name of the OpenAI model to use.
        dimensions: The number of dimensions in the resulting embeddings.
        base_url: Optional base URL for the OpenAI API server.
        api_key_name: Optional name of the environment variable containing the API key.
    """

    implementation: Literal["openai"] = "openai"
    config_type: Literal["embedding"] = "embedding"
    model: str
    dimensions: int
    base_url: str | None = None
    api_key_name: str | None = None

    @classmethod
    def create(
        cls,
        model: str,
        dimensions: int,
        base_url: str | None = None,
        api_key_name: str | None = None,
    ):
        """Create a new OpenAIConfig instance.

        Args:
            model: The name of the OpenAI model to use.
            dimensions: The number of dimensions in the resulting embeddings.
            base_url: Optional base URL for the OpenAI API server.
            api_key_name: Optional name of the environment variable containing the API key.

        Returns:
            A new OpenAIConfig instance.
        """  # noqa: E501
        return cls(
            implementation="openai",
            config_type="embedding",
            model=model,
            dimensions=dimensions,
            base_url=base_url,
            api_key_name=api_key_name,
        )


# Union type representing any of the supported embedding configurations
EmbeddingConfig = SentenceTransformersConfig | OllamaConfig | OpenAIConfig


def embedding_config_from_dict(config: dict[str, Any]) -> EmbeddingConfig:
    """Create an embedding configuration from a dictionary.

    Converts a dictionary representation of an embedding configuration into
    the appropriate EmbeddingConfig object based on the implementation.

    Args:
        config: Dictionary containing configuration parameters.

    Returns:
        An instance of the appropriate EmbeddingConfig subclass.

    Raises:
        AssertionError: If the config is missing an implementation specification.
        ValueError: If the implementation is unrecognized.
    """
    config = {**config, "config_type": "embedding"}
    assert "implementation" in config, "config is missing implementation specification"
    match config["implementation"]:
        case "sentence_transformers":
            return SentenceTransformersConfig(**config)
        case "ollama":
            return OllamaConfig(**config)
        case "openai":
            return OpenAIConfig(**config)
        case _:
            raise ValueError(
                f"Unrecognized embedding implementation: {config['implementation']}"
            )


async def _get_obj_batch(
    con: psycopg.AsyncConnection, catalog_id: int, embedding_name: str, batch_size: int
) -> list[EmbedRow]:
    """Retrieve a batch of database objects that need embedding.

    Fetches database objects (tables, views, procedures, etc.) from the semantic catalog
    that don't yet have embeddings for the specified embedding name.

    Args:
        con: Asynchronous database connection.
        catalog_id: ID of the semantic catalog.
        embedding_name: Name of the embedding column to populate.
        batch_size: Maximum number of objects to retrieve.

    Returns:
        A list of EmbedRow objects containing the object IDs and content to embed.
    """
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            SQL("""\
            select
              id
            , concat_ws
              ( ' '
              , case
                when objargs is not null and array_length(objargs, 1) > 0 then
                    format
                    ( '%%s(%%s)'
                    , array_to_string(objnames, '.')
                    , array_to_string(objargs, ', ')
                    )
                else array_to_string(objnames, '.')
                end
              , description
              ) as content
            from ai.{table}
            where {name} is null
            order by random()
            limit %s
            for update skip locked
        """).format(
                table=Identifier(f"semantic_catalog_obj_{catalog_id}"),
                name=Identifier(embedding_name),
            ),
            (batch_size,),
        )
        batch = [EmbedRow(**row) for row in await cur.fetchall()]
        logger.debug(
            f"got batch of {len(batch)} objects for {embedding_name} of semantic catalog {catalog_id}"  # noqa
        )
        return batch


async def _get_sql_batch(
    con: psycopg.AsyncConnection, catalog_id: int, embedding_name: str, batch_size: int
) -> list[EmbedRow]:
    """Retrieve a batch of SQL examples that need embedding.

    Fetches SQL examples from the semantic catalog that don't yet have embeddings
    for the specified embedding name.

    Args:
        con: Asynchronous database connection.
        catalog_id: ID of the semantic catalog.
        embedding_name: Name of the embedding column to populate.
        batch_size: Maximum number of SQL examples to retrieve.

    Returns:
        A list of EmbedRow objects containing the SQL example IDs and content to embed.
    """
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            SQL("""\
            select
              x.id
            , format
              ( E'%%s\n<sql>\n%%s\n</sql>'
              , x.description
              , x.sql
              ) as content
            from ai.{table} x
            where x.{name} is null
            order by random()
            limit %s
            for update skip locked
        """).format(
                table=Identifier(f"semantic_catalog_sql_{catalog_id}"),
                name=Identifier(embedding_name),
            ),
            (batch_size,),
        )
        batch = [EmbedRow(**row) for row in await cur.fetchall()]
        logger.debug(
            f"got batch of {len(batch)} sql examples for {embedding_name} of semantic catalog {catalog_id}"  # noqa
        )
        return batch


async def _get_fact_batch(
    con: psycopg.AsyncConnection, catalog_id: int, embedding_name: str, batch_size: int
) -> list[EmbedRow]:
    """Retrieve a batch of facts that need embedding.

    Fetches facts from the semantic catalog that don't yet have embeddings
    for the specified embedding name.

    Args:
        con: Asynchronous database connection.
        catalog_id: ID of the semantic catalog.
        embedding_name: Name of the embedding column to populate.
        batch_size: Maximum number of facts to retrieve.

    Returns:
        A list of EmbedRow objects containing the fact IDs and content to embed.
    """
    async with con.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            SQL("""\
            select
              id
            , description as content
            from ai.{table}
            where {name} is null
            order by random()
            limit %s
            for update skip locked
        """).format(
                table=Identifier(f"semantic_catalog_fact_{catalog_id}"),
                name=Identifier(embedding_name),
            ),
            (batch_size,),
        )
        batch = [EmbedRow(**row) for row in await cur.fetchall()]
        logger.debug(
            f"got batch of {len(batch)} facts for {embedding_name} of semantic catalog {catalog_id}"  # noqa
        )
        return batch


async def _get_batch(
    con: psycopg.AsyncConnection,
    catalog_id: int,
    embedding_name: str,
    table: str,
    batch_size: int,
) -> list[EmbedRow]:
    """Get a batch of items to embed based on the table type.

    Dispatches to the appropriate batch retrieval function based on the table type.

    Args:
        con: Asynchronous database connection.
        catalog_id: ID of the semantic catalog.
        embedding_name: Name of the embedding column to populate.
        table: Type of table to retrieve from ("obj", "sql", or "fact").
        batch_size: Maximum number of items to retrieve.

    Returns:
        A list of EmbedRow objects containing the item IDs and content to embed.

    Raises:
        AssertionError: If the table type is not one of the expected values.
        ValueError: If the table type is unrecognized.
    """
    assert table in {"obj", "sql", "fact"}
    match table:
        case "obj":
            return await _get_obj_batch(con, catalog_id, embedding_name, batch_size)
        case "sql":
            return await _get_sql_batch(con, catalog_id, embedding_name, batch_size)
        case "fact":
            return await _get_fact_batch(con, catalog_id, embedding_name, batch_size)
        case _:
            raise ValueError(f"Unrecognized table: {table}")


async def _save_batch(
    con: psycopg.AsyncConnection,
    catalog_id: int,
    embedding_name: str,
    table: str,
    batch: list[EmbedRow],
):
    """Save a batch of embeddings to the database.

    Updates the specified embedding column in the semantic catalog with
    the vector embeddings generated for each item.

    Args:
        con: Asynchronous database connection.
        catalog_id: ID of the semantic catalog.
        embedding_name: Name of the embedding column to update.
        table: Type of table to update ("obj", "sql", or "fact").
        batch: List of EmbedRow objects containing the generated embeddings.

    Raises:
        AssertionError: If the table type is not one of the expected values.
    """
    assert table in {"obj", "sql", "fact"}
    async with con.cursor() as cur:
        logger.debug(
            f"saving batch of {len(batch)} vectors for {embedding_name} of semantic catalog {catalog_id}"  # noqa
        )
        for row in batch:
            await cur.execute(
                SQL("""\
                update ai.{} set {} = %s where id = %s
            """).format(
                    Identifier(f"semantic_catalog_{table}_{catalog_id}"),
                    Identifier(embedding_name),
                ),
                (row.vector, row.id),
            )


async def vectorize(
    con: psycopg.AsyncConnection,
    catalog_id: int,
    embedding_name: str,
    config: EmbeddingConfig,
    batch_size: int = 32,
) -> None:
    """Vectorize content in the semantic catalog.

    Processes all database objects, SQL examples, and facts in the semantic catalog
    that don't yet have embeddings for the specified embedding name. Generates
    embeddings for each item and saves them to the database.

    Args:
        con: Asynchronous database connection.
        catalog_id: ID of the semantic catalog.
        embedding_name: Name of the embedding column to populate.
        config: Configuration for the embedding provider to use.
        batch_size: Number of items to process in each batch (default: 32).
    """
    for table in {"obj", "sql", "fact"}:
        logger.debug(
            f"vectorizing {table} for {embedding_name} of semantic catalog {catalog_id}"
        )
        while True:
            async with con.transaction() as _:
                # TODO: check the db and assert that the embed config still exists and hasn't changed # noqa: E501
                batch = await _get_batch(
                    con, catalog_id, embedding_name, table, batch_size
                )
                if not batch:
                    logger.debug(
                        f"no items found to vectorize for {embedding_name} of semantic catalog {catalog_id}"  # noqa
                    )
                    break
                logger.debug(
                    f"vectorizing {len(batch)} items for {embedding_name} of semantic catalog {catalog_id}"  # noqa
                )
                match config:
                    case SentenceTransformersConfig():
                        from .sentence_tranformers import embed_batch

                        await embed_batch(config, batch)
                    case OllamaConfig():
                        from .ollama import embed_batch

                        await embed_batch(config, batch)
                    case OpenAIConfig():
                        from .openai import embed_batch

                        await embed_batch(config, batch)
                await _save_batch(con, catalog_id, embedding_name, table, batch)
                logger.debug("committing")


async def vectorize_query(config: EmbeddingConfig, query: str) -> Sequence[float]:
    """Generate an embedding for a query string.

    Creates a vector embedding for a query string using the specified embedding provider.
    This is used for semantic search in the catalog.

    Args:
        config: Configuration for the embedding provider to use.
        query: The query string to embed.

    Returns:
        A vector embedding (sequence of floats) for the query.

    Raises:
        ValueError: If the embedding provider configuration is unrecognized.
    """  # noqa: E501
    match config:
        case SentenceTransformersConfig():
            from .sentence_tranformers import embed_query

            return await embed_query(config, query)
        case OllamaConfig():
            from .ollama import embed_query

            return await embed_query(config, query)
        case OpenAIConfig():
            from .openai import embed_query

            return await embed_query(config, query)
        case _:
            raise ValueError(f"Unrecognized config: {config}")
