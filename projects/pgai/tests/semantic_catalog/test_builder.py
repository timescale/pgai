import psycopg

from .utils import PostgresContainer
import pgai.semantic_catalog.builder as builder


async def get_table_names(con: psycopg.AsyncConnection, oids: list[int]) -> set[str]:
    async with con.cursor() as cur:
        await cur.execute("""
            select distinct k.relname
            from pg_class k
            where k.oid = any(%s)
            and k.relkind in ('r', 'p', 'f')
        """, (oids, ))
        return {str(row[0]) for row in await cur.fetchall()}


async def get_view_names(con: psycopg.AsyncConnection, oids: list[int]) -> set[str]:
    async with con.cursor() as cur:
        await cur.execute("""
            select distinct k.relname
            from pg_class k
            where k.oid = any(%s)
            and k.relkind in ('v', 'm')
        """, (oids, ))
        return {str(row[0]) for row in await cur.fetchall()}


async def get_proc_names(con: psycopg.AsyncConnection, oids: list[int]) -> set[str]:
    async with con.cursor() as cur:
        await cur.execute("""
            select distinct p.proname
            from pg_proc p
            where p.oid = any(%s)
        """, (oids, ))
        return {str(row[0]) for row in await cur.fetchall()}


async def test_find_tables_include_schema_no_results(container: PostgresContainer):
    include_schema_args = [
        "public",
        "^public$",
        "public$",
        "^pub"
    ]
    async with await psycopg.AsyncConnection.connect(container.connection_string(database="postgres_air")) as con:
        for arg in include_schema_args:
            oids = await builder.find_tables(con, include_schema=arg)
            assert len(oids) == 0, f"include_schema='{arg}' did not work"


async def test_find_tables_include_schema_results(container: PostgresContainer):
    include_schema_args = [
        None,
        "postgres_air",
        "^postgres_air$",
        "_air$",
    ]
    async with await psycopg.AsyncConnection.connect(container.connection_string(database="postgres_air")) as con:
        for arg in include_schema_args:
            oids = await builder.find_tables(con, include_schema=arg)
            names = await get_table_names(con, oids)
            assert names == {
                'account',
                'aircraft',
                'airport',
                'boarding_pass',
                'booking',
                'booking_leg',
                'flight',
                'frequent_flyer',
                'passenger',
                'phone'
            }, f"include_schema='{arg}' did not work"


async def test_find_tables_exclude_schema_no_results(container: PostgresContainer):
    exclude_schema_args = [
        "public",
        "^public$",
        "public$",
        "^pub"
    ]
    async with await psycopg.AsyncConnection.connect(container.connection_string(database="postgres_air")) as con:
        for arg in exclude_schema_args:
            oids = await builder.find_tables(con, exclude_schema=arg)
            assert len(oids) == 0, f"include_schema='{arg}' did not work"


async def test_find_tables_exclude_schema_results(container: PostgresContainer):
    exclude_schema_args = [
        None,
        "public",
        "^public$",
        "public$",
        "^pub",
        "unknown"
    ]
    async with await psycopg.AsyncConnection.connect(container.connection_string(database="postgres_air")) as con:
        for arg in exclude_schema_args:
            oids = await builder.find_tables(con, exclude_schema=arg)
            names = await get_table_names(con, oids)
            assert names == {
                'account',
                'aircraft',
                'airport',
                'boarding_pass',
                'booking',
                'booking_leg',
                'flight',
                'frequent_flyer',
                'passenger',
                'phone'
            }, f"exclude_schema='{arg}' did not work"
