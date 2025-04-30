import asyncio
import os
from pathlib import Path

import psycopg
import pytest
from psycopg.sql import SQL, Identifier

import pgai
from pgai.semantic_catalog import semantic_catalog
from pgai.semantic_catalog.vectorizer import (
    OllamaConfig,
    OpenAIConfig,
    SentenceTransformersConfig,
    vectorize,
)
from tests.semantic_catalog.utils import PostgresContainer

DATABASE = "sc_03"


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module", autouse=True)
async def setup_database(container: PostgresContainer) -> None:
    container.drop_database(DATABASE, force=True)
    container.create_database(DATABASE)
    pgai.install(container.connection_string(database=DATABASE))
    script = (
        Path(__file__)
        .parent.joinpath("data", "descriptions_to_vectorize.sql")
        .read_text()
    )
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        # create a default semantic catalog
        sc = await semantic_catalog.create(con)
        # add a second embedding config
        await sc.add_embedding(
            con,
            OpenAIConfig.create(
                model="text-embedding-3-small",
                dimensions=1536,
            ),
        )
        # add a third embedding config
        await sc.add_embedding(
            con,
            OllamaConfig.create(
                model="nomic-embed-text",
                dimensions=768,
            ),
        )
        # load descriptions into the semantic catalog
        async with con.cursor() as cur:
            await cur.execute(script)  # pyright: ignore [reportArgumentType]


async def vectorize_test(
    container: PostgresContainer, emb_name: str, emb_type: type
) -> None:
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        async with con.cursor() as cur:
            await cur.execute("""\
                    select count(*) > 0
                    from ai.semantic_catalog_obj_1
                """)
            row = await cur.fetchone()
            assert row is not None
            actual: bool = row[0]
            assert actual > 0, "found no obj rows"
            await cur.execute("""\
                    select count(*) > 0
                    from ai.semantic_catalog_sql_1
                """)
            row = await cur.fetchone()
            assert row is not None
            actual: bool = row[0]
            assert actual > 0, "found no sql rows"
            await cur.execute("""\
                    select count(*) > 0
                    from ai.semantic_catalog_fact_1
                """)
            row = await cur.fetchone()
            assert row is not None
            actual: bool = row[0]
            assert actual > 0, "found no fact rows"
        sc = await semantic_catalog.from_name(con, "default")
        config = await sc.get_embedding(con, emb_name)
        assert config is not None, f"embedding config {emb_name} not found"
        assert isinstance(
            config, emb_type
        ), f"embedding config {emb_name} not of type {emb_type}"
        async with con.cursor() as cur:
            await cur.execute(
                SQL("""\
                select count(*) > 0
                from ai.semantic_catalog_obj_1
                where {} is null
            """).format(Identifier(emb_name))
            )
            assert row is not None
            actual: bool = row[0]
            assert actual is True, f"found no obj rows with null vectors for {emb_name}"
            await cur.execute(
                SQL("""\
                select count(*) > 0
                from ai.semantic_catalog_sql_1
                where {} is null
            """).format(Identifier(emb_name))
            )
            assert row is not None
            actual: bool = row[0]
            assert actual is True, f"found no sql rows with null vectors for {emb_name}"
            await cur.execute(
                SQL("""\
                select count(*) > 0
                from ai.semantic_catalog_fact_1
                where {} is null
            """).format(Identifier(emb_name))
            )
            assert row is not None
            actual: bool = row[0]
            assert (
                actual is True
            ), f"found no fact rows with null vectors for {emb_name}"
        await vectorize(con, sc.id, emb_name, config)
        async with con.cursor() as cur:
            await cur.execute(
                SQL("""\
                select count(*) = 0
                from ai.semantic_catalog_obj_1
                where {} is null
            """).format(Identifier(emb_name))
            )
            assert row is not None
            actual: bool = row[0]
            assert actual is True, f"found obj rows with null vectors for {emb_name}"
            await cur.execute(
                SQL("""\
                select count(*) = 0
                from ai.semantic_catalog_sql_1
                where {} is null
            """).format(Identifier(emb_name))
            )
            assert row is not None
            actual: bool = row[0]
            assert actual is True, f"found sql rows with null vectors for {emb_name}"
            await cur.execute(
                SQL("""\
                select count(*) = 0
                from ai.semantic_catalog_fact_1
                where {} is null
            """).format(Identifier(emb_name))
            )
            assert row is not None
            actual: bool = row[0]
            assert actual is True, f"found fact rows with null vectors for {emb_name}"


async def test_vectorize_sentence_transformers(container: PostgresContainer) -> None:
    await vectorize_test(container, "emb1", SentenceTransformersConfig)


async def test_vectorize_openai(container: PostgresContainer) -> None:
    if "OPENAI_API_KEY" not in os.environ:
        pytest.skip("OPENAI_API_KEY is not set")
    await vectorize_test(container, "emb2", OpenAIConfig)


async def test_vectorize_ollama(container: PostgresContainer) -> None:
    if "OLLAMA_HOST" not in os.environ:
        pytest.skip("OLLAMA_HOST is not set")
    await vectorize_test(container, "emb3", OllamaConfig)
