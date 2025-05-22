import io
import os

import psycopg
import pytest

import pgai
import pgai.semantic_catalog as semantic_catalog
import pgai.semantic_catalog.describe as describe
from pgai.semantic_catalog import file

from .utils import (
    PostgresContainer,
    load_airports,
)

DATABASE = "sc_02"

EMPTY_SET: set[str] = set()

ALL_TABLES: set[str] = {
    "account",
    "aircraft",
    "airport",
    "boarding_pass",
    "booking",
    "booking_leg",
    "events",
    "flight",
    "frequent_flyer",
    "hypertable_test",
    "passenger",
    "phone",
}

ALL_VIEWS: set[str] = {"events_daily", "flight_summary", "passenger_details"}

ALL_PROCS: set[str] = {"advance_air_time", "unsafe_sum", "update_flight_status"}


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
            oids = await describe.find_tables(con, include_extensions=None, **args)
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
        (
            {"include_view": "(passenger_details|flight_summary|events_daily)"},
            ALL_VIEWS,
        ),
        (
            {"exclude_view": "(flight_summary|events_daily)"},
            {"passenger_details"},
        ),
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
            oids = await describe.find_views(con, include_extensions=None, **args)
            actual = await get_view_names(con, oids)
            assert actual == expected, f"find_views with {args} failed"


async def test_find_procs(container: PostgresContainer):
    tests: list[tuple[dict[str, str], set[str]]] = [
        ({"include_schema": "empty"}, EMPTY_SET),
        ({"include_schema": "^empty$"}, EMPTY_SET),
        ({"include_schema": "empty$"}, EMPTY_SET),
        ({"include_schema": "^emp"}, EMPTY_SET),
        ({"include_schema": "postgres_air"}, ALL_PROCS),
        ({"include_schema": "^postgres_air$"}, ALL_PROCS),
        ({"include_schema": "_air$"}, ALL_PROCS),
        ({"exclude_schema": "public"}, ALL_PROCS),
        ({"exclude_schema": "^public$"}, ALL_PROCS),
        ({"exclude_schema": "public$"}, ALL_PROCS),
        ({"exclude_schema": "^pub"}, ALL_PROCS),
        ({"exclude_schema": "(postgres_air|public)"}, EMPTY_SET),
        ({"exclude_schema": "^(postgres_air|public)$"}, EMPTY_SET),
        ({"exclude_schema": "^p"}, EMPTY_SET),
        ({"exclude_schema": "^emp", "include_schema": "_air$"}, ALL_PROCS),
        ({"exclude_schema": "_air$", "include_schema": "^emp"}, EMPTY_SET),
        ({"include_proc": "advance.*"}, {"advance_air_time"}),
        (
            {"include_proc": "(advance_air_time|unsafe_sum|update_flight_status)"},
            ALL_PROCS,
        ),
        (
            {"exclude_proc": "advance_air_time", "include_schema": "postgres_air"},
            {"update_flight_status", "unsafe_sum"},
        ),
        ({"include_proc": "bob"}, EMPTY_SET),
        ({"include_proc": "^advance"}, {"advance_air_time"}),
        ({"exclude_schema": "(postgres_air|public)", "include_proc": ".*"}, EMPTY_SET),
        ({"include_schema": "^postgres_air$", "exclude_proc": ".*"}, EMPTY_SET),
        ({"exclude_schema": "^public$", "exclude_proc": ".*"}, EMPTY_SET),
        (
            {"exclude_schema": "^public$", "include_proc": "^up"},
            {"update_flight_status"},
        ),
    ]
    async with (
        await psycopg.AsyncConnection.connect(
            container.connection_string(database="postgres_air")
        ) as con,
        con.cursor() as cur,
        con.transaction(force_rollback=True) as _,
    ):
        await cur.execute("create schema if not exists empty;")
        for test in tests:
            args, expected = test
            oids = await describe.find_procedures(con, include_extensions=None, **args)
            actual = await get_proc_names(con, oids)
            assert actual == expected, f"find_procs with {args} failed"


async def test_describe(container: PostgresContainer):
    if "ANTHROPIC_API_KEY" not in os.environ:
        pytest.skip("No anthroptic api key provided")
    expected = {
        "postgres_air.airport",
        "postgres_air.airport.airport_code",
        "postgres_air.airport.airport_name",
        "postgres_air.airport.city",
        "postgres_air.airport.airport_tz",
        "postgres_air.airport.continent",
        "postgres_air.airport.iso_country",
        "postgres_air.airport.iso_region",
        "postgres_air.airport.intnl",
        "postgres_air.airport.update_ts",
        "postgres_air.flight_summary",
        "postgres_air.flight_summary.flight_no",
        "postgres_air.flight_summary.departure_airport",
        "postgres_air.flight_summary.arrival_airport",
        "postgres_air.flight_summary.scheduled_departure",
        "postgres_air.advance_air_time",
    }
    buf = io.StringIO()
    async with (
        await psycopg.AsyncConnection.connect(
            container.connection_string(database="postgres_air")
        ) as tcon,
        tcon.transaction(force_rollback=True) as _,
    ):
        await load_airports(tcon)
        _ = await describe.describe(
            container.connection_string(database="postgres_air"),
            model="anthropic:claude-3-7-sonnet-latest",
            output=buf,
            include_schema="postgres_air",
            include_table="airport",
            include_view="flight_summary",
            include_proc="advance_air_time",
        )
    buf.seek(0)
    items = [item for item in file.import_from_yaml(buf)]
    assert len(items) == 3
    container.drop_database(DATABASE, force=True)
    container.create_database(DATABASE)
    pgai.install(container.connection_string(database=DATABASE))
    async with (
        await psycopg.AsyncConnection.connect(
            container.connection_string(database="postgres_air")
        ) as tcon,
        await psycopg.AsyncConnection.connect(
            container.connection_string(database=DATABASE)
        ) as ccon,
        ccon.cursor() as cur,
    ):
        sc = await semantic_catalog.create(ccon)
        await file.save_to_catalog(ccon, tcon, sc.id, iter(items))
        await cur.execute("""\
            select array_to_string(objnames, '.')
            from ai.semantic_catalog_obj_1
            where description is not null
        """)
        actual = {row[0] for row in await cur.fetchall()}
    assert actual == expected
