from pathlib import Path

import psycopg

from pgai.semantic_catalog import render
from pgai.semantic_catalog.models import Description

from .utils import PostgresContainer, get_procedures, get_tables, get_views


def test_render_tables():
    tables = get_tables()
    actual = render.render_tables(tables)
    Path(__file__).parent.joinpath("render_tables.actual").write_text(actual)
    expected = Path(__file__).parent.joinpath("render_tables.expected").read_text()
    assert actual == expected


def test_render_views():
    views = get_views()
    actual = render.render_views(views)
    Path(__file__).parent.joinpath("render_views.actual").write_text(actual)
    expected = Path(__file__).parent.joinpath("render_views.expected").read_text()
    assert actual == expected


def test_render_procedures():
    procedures = get_procedures()
    actual = render.render_procedures(procedures)
    Path(__file__).parent.joinpath("render_procedures.actual").write_text(actual)
    expected = Path(__file__).parent.joinpath("render_procedures.expected").read_text()
    assert actual == expected


async def test_render_description_to_sql(container: PostgresContainer):
    actual = Path(__file__).parent.joinpath("render_description_to_sql.actual")
    with actual.open("w") as f:
        async with await psycopg.AsyncConnection.connect(
            container.connection_string(database="postgres_air")
        ) as con:
            for i, table in enumerate(get_tables()):
                desc = Description(
                    classid=42,
                    objid=i,
                    objsubid=0,
                    objtype="table",
                    objnames=[table.schema_name, table.table_name],
                    objargs=[],
                    description=f"this is a description for table {table.table_name}",
                )
                f.write(render.render_description_to_sql(con, "my_catalog", desc))
                for col in table.columns:
                    desc = Description(
                        classid=42,
                        objid=i,
                        objsubid=col.objsubid,
                        objtype="table column",
                        objnames=[table.schema_name, table.table_name, col.name],
                        objargs=[],
                        description=f"this is a description for column {col.name}",
                    )
                    f.write(render.render_description_to_sql(con, "my_catalog", desc))
            for i, view in enumerate(get_views()):
                desc = Description(
                    classid=42,
                    objid=i + 100,
                    objsubid=0,
                    objtype="view",
                    objnames=[view.schema_name, view.view_name],
                    objargs=[],
                    description=f"this is a description for view {view.view_name}",
                )
                f.write(render.render_description_to_sql(con, "my_catalog", desc))
                for col in view.columns:
                    desc = Description(
                        classid=42,
                        objid=i,
                        objsubid=col.objsubid,
                        objtype="view column",
                        objnames=[view.schema_name, view.view_name, col.name],
                        objargs=[],
                        description=f"this is a description for column {col.name}",
                    )
                    f.write(render.render_description_to_sql(con, "my_catalog", desc))
            for i, procedure in enumerate(get_procedures()):
                desc = Description(
                    classid=666,
                    objid=i,
                    objsubid=0,
                    objtype=procedure.kind,
                    objnames=[procedure.schema_name, procedure.proc_name],
                    objargs=procedure.objargs,
                    description=f"this is a description for {procedure.kind} {procedure.proc_name}",  # noqa: E501
                )
                f.write(render.render_description_to_sql(con, "my_catalog", desc))
    actual = actual.read_text()
    expected = (
        Path(__file__).parent.joinpath("render_description_to_sql.expected").read_text()
    )
    assert actual == expected


async def test_render_description_to_comment(container: PostgresContainer):
    actual = Path(__file__).parent.joinpath("render_description_to_comment.actual")
    with actual.open("w") as f:
        async with await psycopg.AsyncConnection.connect(
            container.connection_string(database="postgres_air")
        ) as con:
            for i, table in enumerate(get_tables()):
                desc = Description(
                    classid=42,
                    objid=i,
                    objsubid=0,
                    objtype="table",
                    objnames=[table.schema_name, table.table_name],
                    objargs=[],
                    description=f"this is a description for table {table.table_name}",
                )
                f.write(render.render_description_to_comment(con, desc))
                for col in table.columns:
                    desc = Description(
                        classid=42,
                        objid=i,
                        objsubid=col.objsubid,
                        objtype="table column",
                        objnames=[table.schema_name, table.table_name, col.name],
                        objargs=[],
                        description=f"this is a description for column {col.name}",
                    )
                    f.write(render.render_description_to_comment(con, desc))
            for i, view in enumerate(get_views()):
                desc = Description(
                    classid=42,
                    objid=i + 100,
                    objsubid=0,
                    objtype="view",
                    objnames=[view.schema_name, view.view_name],
                    objargs=[],
                    description=f"this is a description for view {view.view_name}",
                )
                f.write(render.render_description_to_comment(con, desc))
                for col in view.columns:
                    desc = Description(
                        classid=42,
                        objid=i,
                        objsubid=col.objsubid,
                        objtype="view column",
                        objnames=[view.schema_name, view.view_name, col.name],
                        objargs=[],
                        description=f"this is a description for column {col.name}",
                    )
                    f.write(render.render_description_to_comment(con, desc))
            for i, procedure in enumerate(get_procedures()):
                desc = Description(
                    classid=666,
                    objid=i,
                    objsubid=0,
                    objtype=procedure.kind,
                    objnames=[procedure.schema_name, procedure.proc_name],
                    objargs=procedure.objargs,
                    description=f"this is a description for {procedure.kind} {procedure.proc_name}",  # noqa: E501
                )
                f.write(render.render_description_to_comment(con, desc))
    actual = actual.read_text()
    expected = (
        Path(__file__)
        .parent.joinpath("render_description_to_comment.expected")
        .read_text()
    )
    assert actual == expected
