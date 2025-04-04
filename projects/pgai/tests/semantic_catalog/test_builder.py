import psycopg

import pgai.semantic_catalog.builder as builder

from .utils import PostgresContainer

EMPTY_SET: set[str] = set()

ALL_TABLES: set[str] = {
    "account",
    "aircraft",
    "airport",
    "boarding_pass",
    "booking",
    "booking_leg",
    "flight",
    "frequent_flyer",
    "passenger",
    "phone",
}

ALL_VIEWS: set[str] = {"flight_summary", "passenger_details"}

ALL_PROCS: set[str] = {"advance_air_time", "update_flight_status"}


async def get_table_names(con: psycopg.AsyncConnection, oids: list[int]) -> set[str]:
    async with con.cursor() as cur:
        await cur.execute(
            """
            select distinct k.relname
            from pg_class k
            where k.oid = any(%s)
            and k.relkind in ('r', 'p', 'f')
        """,
            (oids,),
        )
        return {str(row[0]) for row in await cur.fetchall()}


async def get_view_names(con: psycopg.AsyncConnection, oids: list[int]) -> set[str]:
    async with con.cursor() as cur:
        await cur.execute(
            """
            select distinct k.relname
            from pg_class k
            where k.oid = any(%s)
            and k.relkind in ('v', 'm')
        """,
            (oids,),
        )
        return {str(row[0]) for row in await cur.fetchall()}


async def get_proc_names(con: psycopg.AsyncConnection, oids: list[int]) -> set[str]:
    async with con.cursor() as cur:
        await cur.execute(
            """
            select distinct p.proname
            from pg_proc p
            where p.oid = any(%s)
        """,
            (oids,),
        )
        return {str(row[0]) for row in await cur.fetchall()}


async def test_find_tables(container: PostgresContainer):
    tests: list[tuple[dict[str, str], set[str]]] = [
        ({"include_schema": "public"}, EMPTY_SET),
        ({"include_schema": "^public$"}, EMPTY_SET),
        ({"include_schema": "public$"}, EMPTY_SET),
        ({"include_schema": "^pub"}, EMPTY_SET),
        ({"include_schema": "postgres_air"}, ALL_TABLES),
        ({"include_schema": "^postgres_air$"}, ALL_TABLES),
        ({"include_schema": "_air$"}, ALL_TABLES),
        ({"exclude_schema": "public"}, ALL_TABLES),
        ({"exclude_schema": "^public$"}, ALL_TABLES),
        ({"exclude_schema": "public$"}, ALL_TABLES),
        ({"exclude_schema": "^pub"}, ALL_TABLES),
        ({"exclude_schema": "postgres_air"}, EMPTY_SET),
        ({"exclude_schema": "^postgres_air$"}, EMPTY_SET),
        ({"exclude_schema": "_air$"}, EMPTY_SET),
        ({"exclude_schema": "^pub", "include_schema": "_air$"}, ALL_TABLES),
        ({"exclude_schema": "_air$", "include_schema": "^pub"}, EMPTY_SET),
        ({"include_table": ".*"}, ALL_TABLES),
        ({"include_table": "(airport|aircraft)"}, {"airport", "aircraft"}),
        ({"exclude_table": "(airport|aircraft)"}, ALL_TABLES - {"airport", "aircraft"}),
        ({"include_table": "bob"}, EMPTY_SET),
        ({"include_table": "^booking"}, {"booking", "booking_leg"}),
        ({"exclude_schema": "_air$", "include_table": ".*"}, EMPTY_SET),
        ({"include_schema": "^postgres_air$", "exclude_table": ".*"}, EMPTY_SET),
        ({"exclude_schema": "^public$", "exclude_table": ".*"}, EMPTY_SET),
        (
            {"exclude_schema": "^public$", "include_table": "^a"},
            {"account", "aircraft", "airport"},
        ),
    ]
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database="postgres_air")
    ) as con:
        for test in tests:
            args, expected = test
            oids = await builder.find_tables(con, **args)
            actual = await get_table_names(con, oids)
            assert actual == expected, f"find_tables with {args} failed"


async def test_find_views(container: PostgresContainer):
    tests: list[tuple[dict[str, str], set[str]]] = [
        ({"include_schema": "public"}, EMPTY_SET),
        ({"include_schema": "^public$"}, EMPTY_SET),
        ({"include_schema": "public$"}, EMPTY_SET),
        ({"include_schema": "^pub"}, EMPTY_SET),
        ({"include_schema": "postgres_air"}, ALL_VIEWS),
        ({"include_schema": "^postgres_air$"}, ALL_VIEWS),
        ({"include_schema": "_air$"}, ALL_VIEWS),
        ({"exclude_schema": "public"}, ALL_VIEWS),
        ({"exclude_schema": "^public$"}, ALL_VIEWS),
        ({"exclude_schema": "public$"}, ALL_VIEWS),
        ({"exclude_schema": "^pub"}, ALL_VIEWS),
        ({"exclude_schema": "postgres_air"}, EMPTY_SET),
        ({"exclude_schema": "^postgres_air$"}, EMPTY_SET),
        ({"exclude_schema": "_air$"}, EMPTY_SET),
        ({"exclude_schema": "^pub", "include_schema": "_air$"}, ALL_VIEWS),
        ({"exclude_schema": "_air$", "include_schema": "^pub"}, EMPTY_SET),
        ({"include_view": ".*"}, ALL_VIEWS),
        ({"include_view": "(passenger_details|flight_summary)"}, ALL_VIEWS),
        ({"exclude_view": "flight_summary"}, {"passenger_details"}),
        ({"include_view": "bob"}, EMPTY_SET),
        ({"include_view": "^flight"}, {"flight_summary"}),
        ({"exclude_schema": "_air$", "include_view": ".*"}, EMPTY_SET),
        ({"include_schema": "^postgres_air$", "exclude_view": ".*"}, EMPTY_SET),
        ({"exclude_schema": "^public$", "exclude_view": ".*"}, EMPTY_SET),
        ({"exclude_schema": "^public$", "include_view": "^f"}, {"flight_summary"}),
    ]
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database="postgres_air")
    ) as con:
        for test in tests:
            args, expected = test
            oids = await builder.find_views(con, **args)
            actual = await get_view_names(con, oids)
            assert actual == expected, f"find_views with {args} failed"


async def test_find_procs(container: PostgresContainer):
    tests: list[tuple[dict[str, str], set[str]]] = [
        ({"include_schema": "public"}, EMPTY_SET),
        ({"include_schema": "^public$"}, EMPTY_SET),
        ({"include_schema": "public$"}, EMPTY_SET),
        ({"include_schema": "^pub"}, EMPTY_SET),
        ({"include_schema": "postgres_air"}, ALL_PROCS),
        ({"include_schema": "^postgres_air$"}, ALL_PROCS),
        ({"include_schema": "_air$"}, ALL_PROCS),
        ({"exclude_schema": "public"}, ALL_PROCS),
        ({"exclude_schema": "^public$"}, ALL_PROCS),
        ({"exclude_schema": "public$"}, ALL_PROCS),
        ({"exclude_schema": "^pub"}, ALL_PROCS),
        ({"exclude_schema": "postgres_air"}, EMPTY_SET),
        ({"exclude_schema": "^postgres_air$"}, EMPTY_SET),
        ({"exclude_schema": "_air$"}, EMPTY_SET),
        ({"exclude_schema": "^pub", "include_schema": "_air$"}, ALL_PROCS),
        ({"exclude_schema": "_air$", "include_schema": "^pub"}, EMPTY_SET),
        ({"include_proc": ".*"}, ALL_PROCS),
        ({"include_proc": "(advance_air_time|update_flight_status)"}, ALL_PROCS),
        ({"exclude_proc": "advance_air_time"}, {"update_flight_status"}),
        ({"include_proc": "bob"}, EMPTY_SET),
        ({"include_proc": "^advance"}, {"advance_air_time"}),
        ({"exclude_schema": "_air$", "include_proc": ".*"}, EMPTY_SET),
        ({"include_schema": "^postgres_air$", "exclude_proc": ".*"}, EMPTY_SET),
        ({"exclude_schema": "^public$", "exclude_proc": ".*"}, EMPTY_SET),
        (
            {"exclude_schema": "^public$", "include_proc": "^u"},
            {"update_flight_status"},
        ),
    ]
    async with await psycopg.AsyncConnection.connect(
        container.connection_string(database="postgres_air")
    ) as con:
        for test in tests:
            args, expected = test
            oids = await builder.find_procedures(con, **args)
            actual = await get_proc_names(con, oids)
            assert actual == expected, f"find_procs with {args} failed"
