import psycopg

from pgai.semantic_catalog import builder, loader

from .utils import PostgresContainer, get_procedures, get_tables, get_views


async def test_load_tables(container: PostgresContainer):
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database="postgres_air")
    ) as con:
        for table_name, expected in get_tables().items():
            oids = await builder.find_tables(con, include_table=table_name)
            actual = await loader.load_tables(con, oids)
            actual = actual[0]
            actual.id = None
            assert actual == expected, f"load_tables failed for {table_name}"


async def test_load_views(container: PostgresContainer):
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database="postgres_air")
    ) as con:
        for view_name, expected in get_views().items():
            oids = await builder.find_views(con, include_view=view_name)
            actual = await loader.load_views(con, oids)
            actual = actual[0]
            actual.id = None
            assert actual == expected, f"load_views failed for {view_name}"


async def test_load_procedures(container: PostgresContainer):
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database="postgres_air")
    ) as con:
        for proc_name, expected in get_procedures().items():
            oids = await builder.find_procedures(con, include_proc=proc_name)
            actual = await loader.load_procedures(con, oids)
            actual = actual[0]
            actual.id = None
            assert actual == expected, f"load_procs failed for {proc_name}"
