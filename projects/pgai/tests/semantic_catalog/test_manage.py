import asyncio

import psycopg
import pytest

import pgai
from pgai.semantic_catalog import semantic_catalog
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
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        await semantic_catalog.create(con)


async def test_fact(container: PostgresContainer) -> None:
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        fact = await sc.add_fact(
            con,
            "This is a test fact",
        )
        assert fact is not None
        assert fact.id is not None
        assert fact.description == "This is a test fact"

        facts = await sc.list_facts(con)
        assert len(facts) == 1

        edit_fact = await sc.update_fact(con, fact.id, "This is an updated test fact")
        assert edit_fact is not None
        assert edit_fact.id == fact.id
        assert edit_fact.description == "This is an updated test fact"

        await sc.drop_fact(con, fact.id)

        facts = await sc.list_facts(con)
        assert len(facts) == 0


async def test_update_nonexistant_fact_errors(container: PostgresContainer) -> None:
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        with pytest.raises(RuntimeError):
            await sc.update_fact(
                con,
                9999,
                "Fact with id 9999 not found in catalog default"
            )
