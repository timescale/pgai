import logging
from collections.abc import Sequence
from typing import Annotated, Any, Literal

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier
from pydantic import BaseModel, Field

from pgai.semantic_catalog.vectorizer.models import EmbedRow

logger = logging.getLogger(__name__)


class SentenceTransformersConfig(BaseModel):
    implementation: Literal["sentence_transformers"]
    config_type: Literal["embedding"]
    model: str
    dimensions: int

    @classmethod
    def create(cls, model: str, dimensions: int):
        return cls(
            implementation="sentence_transformers",
            config_type="embedding",
            model=model,
            dimensions=dimensions,
        )


class OllamaConfig(BaseModel):
    implementation: Literal["ollama"]
    config_type: Literal["embedding"]
    model: str
    dimensions: int
    base_url: str | None = None

    @classmethod
    def create(cls, model: str, dimensions: int, base_url: str | None = None):
        return cls(
            implementation="ollama",
            config_type="embedding",
            model=model,
            dimensions=dimensions,
            base_url=base_url,
        )


class OpenAIConfig(BaseModel):
    implementation: Literal["openai"]
    config_type: Literal["embedding"]
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
        return cls(
            implementation="openai",
            config_type="embedding",
            model=model,
            dimensions=dimensions,
            base_url=base_url,
            api_key_name=api_key_name,
        )


EmbeddingConfig = Annotated[
    SentenceTransformersConfig | OllamaConfig | OpenAIConfig,
    Field(discriminator="implementation"),
]


def embedding_config_from_dict(config: dict[str, Any]) -> EmbeddingConfig:
    assert "implementation" in config
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
