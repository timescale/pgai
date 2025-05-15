import asyncio
import os
from pathlib import Path

import psycopg
import pytest

import pgai
import pgai.semantic_catalog.search as search
from pgai.semantic_catalog import semantic_catalog
from pgai.semantic_catalog.vectorizer import (
    OllamaConfig,
    OpenAIConfig,
    SentenceTransformersConfig,
    vectorize_query,
)
from tests.semantic_catalog.utils import PostgresContainer

DATABASE = "sc_04"


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
    script = Path(__file__).parent.joinpath("data", "vector_dump.sql").read_text()
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
        # load descriptions+vectors into the semantic catalog
        async with con.cursor() as cur:
            await cur.execute(script)  # pyright: ignore [reportArgumentType]


async def test_list_objects(container: PostgresContainer) -> None:
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        obj_descs = await sc.list_objects(con)
        assert len(obj_descs) > 0
        obj_desc = obj_descs[0]
        assert obj_desc.objnames == ["postgres_air", "airport"]
        assert obj_desc.description is not None


async def test_list_objects_objtype(container: PostgresContainer) -> None:
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        obj_descs = await sc.list_objects(con, objtype="table column")
        assert len(obj_descs) > 0
        obj_desc = obj_descs[0]
        assert obj_desc.objnames == ["postgres_air", "airport", "airport_code"]
        assert obj_desc.description is not None


async def test_search_obj_sentence_transformers(container: PostgresContainer) -> None:
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        emb_cfg = await sc.get_embedding(con, "emb1")
        assert isinstance(emb_cfg, SentenceTransformersConfig)
        vec = await vectorize_query(
            emb_cfg, "What column will tell me if an airport is international?"
        )
        obj_descs = await search.search_objects(con, sc.id, "emb1", emb_cfg, vec)
        assert len(obj_descs) > 0
        obj_desc = obj_descs[0]
        assert obj_desc.objnames == ["postgres_air", "airport", "intnl"]
        assert obj_desc.description is not None


async def test_search_obj_openai(container: PostgresContainer) -> None:
    if "OPENAI_API_KEY" not in os.environ:
        pytest.skip("OPENAI_API_KEY is not set")
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        emb_cfg = await sc.get_embedding(con, "emb2")
        assert isinstance(emb_cfg, OpenAIConfig)
        vec = await vectorize_query(
            emb_cfg, "What column will tell me if an airport is international?"
        )
        obj_descs = await search.search_objects(con, sc.id, "emb2", emb_cfg, vec)
        assert len(obj_descs) > 0
        obj_desc = obj_descs[0]
        assert obj_desc.objnames == ["postgres_air", "airport", "intnl"]
        assert obj_desc.description is not None


async def test_search_obj_ollama(container: PostgresContainer) -> None:
    if "OLLAMA_HOST" not in os.environ:
        pytest.skip("OLLAMA_HOST is not set")
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        emb_cfg = await sc.get_embedding(con, "emb3")
        assert isinstance(emb_cfg, OllamaConfig)
        vec = await vectorize_query(
            emb_cfg, "What column will tell me if an airport is international?"
        )
        obj_descs = await search.search_objects(con, sc.id, "emb3", emb_cfg, vec)
        assert len(obj_descs) > 0
        obj_desc = obj_descs[0]
        assert obj_desc.objnames == ["postgres_air", "airport", "intnl"]
        assert obj_desc.description is not None


async def test_list_sql(container: PostgresContainer) -> None:
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        sql_examples = await sc.list_sql_examples(con)
        assert len(sql_examples) > 0
        sql_example = sql_examples[0]
        assert (
            sql_example.description == "Delayed flights are indicated by their status"
        )


async def test_search_sql_sentence_transformers(container: PostgresContainer) -> None:
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        emb_cfg = await sc.get_embedding(con, "emb1")
        assert isinstance(emb_cfg, SentenceTransformersConfig)
        vec = await vectorize_query(emb_cfg, "Is my flight delayed?")
        sql_examples = await search.search_sql_examples(
            con, sc.id, "emb1", emb_cfg, vec
        )
        assert len(sql_examples) > 0
        sql_example = sql_examples[0]
        assert (
            sql_example.description == "Delayed flights are indicated by their status"
        )


async def test_search_sql_openai(container: PostgresContainer) -> None:
    if "OPENAI_API_KEY" not in os.environ:
        pytest.skip("OPENAI_API_KEY is not set")
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        emb_cfg = await sc.get_embedding(con, "emb2")
        assert isinstance(emb_cfg, OpenAIConfig)
        vec = await vectorize_query(emb_cfg, "Is my flight delayed?")
        sql_examples = await search.search_sql_examples(
            con, sc.id, "emb2", emb_cfg, vec
        )
        assert len(sql_examples) > 0
        sql_example = sql_examples[0]
        assert (
            sql_example.description == "Delayed flights are indicated by their status"
        )


async def test_search_sql_ollama(container: PostgresContainer) -> None:
    if "OLLAMA_HOST" not in os.environ:
        pytest.skip("OLLAMA_HOST is not set")
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        emb_cfg = await sc.get_embedding(con, "emb3")
        assert isinstance(emb_cfg, OllamaConfig)
        vec = await vectorize_query(emb_cfg, "Is my flight delayed?")
        sql_examples = await search.search_sql_examples(
            con, sc.id, "emb3", emb_cfg, vec
        )
        assert len(sql_examples) > 0
        sql_example = sql_examples[0]
        assert (
            sql_example.description == "Delayed flights are indicated by their status"
        )


async def test_list_facts(container: PostgresContainer) -> None:
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        facts = await sc.list_facts(con)
        assert len(facts) > 0
        fact = facts[0]
        assert (
            fact.description
            == "The postgres_air.airport.iso_region values are in uppercase."
        )


async def test_search_fact_sentence_transformers(container: PostgresContainer) -> None:
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        emb_cfg = await sc.get_embedding(con, "emb1")
        assert isinstance(emb_cfg, SentenceTransformersConfig)
        vec = await vectorize_query(emb_cfg, "What airports are in the Texas region?")
        facts = await search.search_facts(con, sc.id, "emb1", emb_cfg, vec)
        assert len(facts) > 0
        fact = facts[0]
        assert (
            fact.description
            == "The postgres_air.airport.iso_region values are in uppercase."
        )


async def test_search_fact_openai(container: PostgresContainer) -> None:
    if "OPENAI_API_KEY" not in os.environ:
        pytest.skip("OPENAI_API_KEY is not set")
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        emb_cfg = await sc.get_embedding(con, "emb2")
        assert isinstance(emb_cfg, OpenAIConfig)
        vec = await vectorize_query(emb_cfg, "What airports are in the Texas region?")
        facts = await search.search_facts(con, sc.id, "emb2", emb_cfg, vec)
        assert len(facts) > 0
        fact = facts[0]
        assert (
            fact.description
            == "The postgres_air.airport.iso_region values are in uppercase."
        )


async def test_search_fact_ollama(container: PostgresContainer) -> None:
    if "OLLAMA_HOST" not in os.environ:
        pytest.skip("OLLAMA_HOST is not set")
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        emb_cfg = await sc.get_embedding(con, "emb3")
        assert isinstance(emb_cfg, OllamaConfig)
        vec = await vectorize_query(emb_cfg, "What airports are in the Texas region?")
        facts = await search.search_facts(con, sc.id, "emb3", emb_cfg, vec)
        assert len(facts) > 0
        fact = facts[0]
        assert (
            fact.description
            == "The postgres_air.airport.iso_region values are in uppercase."
        )
