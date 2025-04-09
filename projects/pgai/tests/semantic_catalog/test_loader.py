import json
from pathlib import Path

import psycopg

from pgai.semantic_catalog import loader, builder
from pgai.semantic_catalog.models import Table, View, Procedure

from .utils import PostgresContainer


async def gen_tables_json(container: PostgresContainer):
    stuff = {}
    async with await psycopg.AsyncConnection.connect(container.connection_string(database="postgres_air")) as con:
        oids = await builder.find_tables(con)
        tables = await loader.load_tables(con, oids)
        for table in tables:
            stuff[table.table_name] = table.dict(exclude={'id'})
    Path(__file__).parent.joinpath("tables.json").write_text(json.dumps(stuff, indent=2))


async def gen_views_json(container: PostgresContainer):
    stuff = {}
    async with await psycopg.AsyncConnection.connect(container.connection_string(database="postgres_air")) as con:
        oids = await builder.find_views(con)
        views = await loader.load_views(con, oids)
        for view in views:
            stuff[view.view_name] = view.dict(exclude={'id'})
    Path(__file__).parent.joinpath("views.json").write_text(json.dumps(stuff, indent=2))


async def gen_procs_json(container: PostgresContainer):
    stuff = {}
    async with await psycopg.AsyncConnection.connect(container.connection_string(database="postgres_air")) as con:
        oids = await builder.find_procedures(con)
        procs = await loader.load_procedures(con, oids)
        for proc in procs:
            stuff[proc.proc_name] = proc.dict(exclude={'id'})
    Path(__file__).parent.joinpath("procedures.json").write_text(json.dumps(stuff, indent=2))


def get_tables() -> dict[str, Table]:
    raw: dict = json.loads(Path(__file__).parent.joinpath("tables.json").read_text())
    return {k: Table(id=None, **v) for k, v in raw.items()}


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


def get_views() -> dict[str, View]:
    raw: dict = json.loads(Path(__file__).parent.joinpath("views.json").read_text())
    return {k: View(id=None, **v) for k, v in raw.items()}


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


def get_procedures() -> dict[str, Procedure]:
    raw: dict = json.loads(Path(__file__).parent.joinpath("procedures.json").read_text())
    return {k: Procedure(id=None, **v) for k, v in raw.items()}


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
