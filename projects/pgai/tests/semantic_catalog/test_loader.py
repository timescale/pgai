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
            assert len(actual) == 1
            actual = actual[0]
            # classid and objid will change. don't compare
            actual.classid = expected.classid
            actual.objid = expected.objid
            for column in actual.columns:
                column.classid = expected.classid
                column.objid = expected.objid
            assert actual == expected, f"load_tables failed for {table_name}"


async def test_load_views(container: PostgresContainer):
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database="postgres_air")
    ) as con:
        for view_name, expected in get_views().items():
            oids = await builder.find_views(con, include_view=view_name)
            assert len(oids) == 1
            actual = await loader.load_views(con, oids)
            assert len(actual) == 1
            actual = actual[0]
            # classid and objid will change. don't compare
            actual.classid = expected.classid
            actual.objid = expected.objid
            for column in actual.columns:
                column.classid = expected.classid
                column.objid = expected.objid
            assert actual == expected, f"load_views failed for {view_name}"


async def test_load_procedures(container: PostgresContainer):
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database="postgres_air")
    ) as con:
        for proc_name, expected in get_procedures().items():
            oids = await builder.find_procedures(con, include_proc=proc_name)
            assert len(oids) == 1
            actual = await loader.load_procedures(con, oids)
            assert len(actual) == 1
            actual = actual[0]
            # classid and objid will change. don't compare
            actual.classid = expected.classid
            actual.objid = expected.objid
            assert actual == expected, f"load_procs failed for {proc_name}"
