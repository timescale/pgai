from collections.abc import Sequence
from typing import Annotated, Any, Literal

import psycopg
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier
from pydantic import BaseModel, Field


class SentenceTransformersConfig(BaseModel):
    implementation: Literal["sentence_transformers"]
    config_type: Literal["embedding"]
    model: str
    dimensions: int


class OllamaConfig(BaseModel):
    implementation: Literal["ollama"]
    config_type: Literal["embedding"]
    model: str
    dimensions: int
    base_url: str | None = None


class OpenAIConfig(BaseModel):
    implementation: Literal["openai"]
    config_type: Literal["embedding"]
    model: str
    dimensions: int
    base_url: str | None = None
    api_key_name: str | None = None


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


class EmbedRow(BaseModel):
    id: int
    content: str
    vector: Sequence[float] | None = None


async def _get_obj_batch(
    con: psycopg.AsyncConnection, id: int, name: str, batch_size: int
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
                table=Identifier(f"semantic_catalog_obj_{id}"), name=Identifier(name)
            ),
            (batch_size,),
        )
        return [EmbedRow(**row) for row in await cur.fetchall()]


async def _get_sql_batch(
    con: psycopg.AsyncConnection, id: int, name: str, batch_size: int
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
                table=Identifier(f"semantic_catalog_sql_{id}"), name=Identifier(name)
            ),
            (batch_size,),
        )
        return [EmbedRow(**row) for row in await cur.fetchall()]


async def _get_fact_batch(
    con: psycopg.AsyncConnection, id: int, name: str, batch_size: int
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
                table=Identifier(f"semantic_catalog_fact_{id}"), name=Identifier(name)
            ),
            (batch_size,),
        )
        return [EmbedRow(**row) for row in await cur.fetchall()]


async def _get_batch(
    con: psycopg.AsyncConnection, id: int, name: str, table: str, batch_size: int
) -> list[EmbedRow]:
    assert table in {"obj", "sql", "fact"}
    match table:
        case "obj":
            return await _get_obj_batch(con, id, name, batch_size)
        case "sql":
            return await _get_sql_batch(con, id, name, batch_size)
        case "fact":
            return await _get_fact_batch(con, id, name, batch_size)
        case _:
            raise ValueError(f"Unrecognized table: {table}")


async def _save_batch(
    con: psycopg.AsyncConnection, id: int, name: str, table: str, batch: list[EmbedRow]
):
    assert table in {"obj", "sql", "fact"}
    async with con.cursor() as cur:
        for row in batch:
            await cur.execute(
                SQL("""\
                update ai.{} set {} = %s where id = %s
            """).format(Identifier(f"semantic_catalog_{table}_{id}"), Identifier(name)),
                (row.vector, row.id),
            )


async def vectorize(
    con: psycopg.AsyncConnection,
    id: int,
    name: str,
    config: EmbeddingConfig,
    batch_size: int = 32,
) -> None:
    for table in {"obj", "sql", "fact"}:
        while True:
            async with con.transaction() as _:
                # TODO: check the db and assert that the embed config still exists and hasn't changed # noqa: E501
                batch = await _get_batch(con, id, name, table, batch_size)
                if not batch:
                    break
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
                await _save_batch(con, id, name, table, batch)


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
