import asyncio

import psycopg
import pytest

import pgai
from pgai.semantic_catalog import semantic_catalog
from tests.semantic_catalog.utils import PostgresContainer

DATABASE = "sc_" + __name__.split(".")[-1]


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


async def test_object(container: PostgresContainer) -> None:
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        obj = await sc.add_object(
            con,
            1234,
            5678,
            1256,
            "table",
            ["public", "test_object"],
            [],
            "This is a test object",
        )
        assert obj is not None
        assert obj.id is not None
        assert obj.classid == 1234
        assert obj.objid == 5678
        assert obj.objsubid == 1256
        assert obj.objtype == "table"
        assert obj.objnames == ["public", "test_object"]
        assert obj.objargs == []
        assert obj.description == "This is a test object"

        objects = await sc.list_objects(con)
        assert len(objects) == 1

        edit_obj = await sc.update_object(con, obj.id, "This is an updated test object")
        assert edit_obj is not None
        assert edit_obj.id == obj.id
        assert edit_obj.description == "This is an updated test object"

        await sc.drop_object(con, obj.id)

        objects = await sc.list_objects(con)
        assert len(objects) == 0


async def test_object_not_found_errors(container: PostgresContainer) -> None:
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        with pytest.raises(RuntimeError):
            await sc.update_object(
                con, 9999, "Object with id 9999 not found in catalog default"
            )


async def test_sql_example(container: PostgresContainer) -> None:
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        sql_example = await sc.add_sql_example(
            con,
            "SELECT 1",
            "This is a test SQL example",
        )
        assert sql_example is not None
        assert sql_example.id is not None
        assert sql_example.description == "This is a test SQL example"
        assert sql_example.sql == "SELECT 1"

        sql_examples = await sc.list_sql_examples(con)
        assert len(sql_examples) == 1

        edit_sql_example = await sc.update_sql_example(
            con,
            sql_example.id,
            "SELECT 2",
        )
        assert edit_sql_example is not None
        assert edit_sql_example.id == sql_example.id
        assert edit_sql_example.description == "This is a test SQL example"
        assert edit_sql_example.sql == "SELECT 2"

        edit_sql_example = await sc.update_sql_example(
            con, sql_example.id, description="This is an updated test SQL example"
        )
        assert edit_sql_example is not None
        assert edit_sql_example.id == sql_example.id
        assert edit_sql_example.description == "This is an updated test SQL example"
        assert edit_sql_example.sql == "SELECT 2"

        await sc.drop_sql_example(con, sql_example.id)
        sql_examples = await sc.list_sql_examples(con)
        assert len(sql_examples) == 0


async def test_sql_example_not_found_errors(container: PostgresContainer) -> None:
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database=DATABASE)
    ) as con:
        sc = await semantic_catalog.from_name(con, "default")
        with pytest.raises(RuntimeError):
            await sc.update_sql_example(con, 9999, "SELECT 1")


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
                con, 9999, "Fact with id 9999 not found in catalog default"
            )
