from pathlib import Path

from pgai.semantic_catalog import render
from pgai.semantic_catalog.models import Procedure, Table, View

from .utils import get_procedures, get_tables, get_views


def test_render_tables():
    table_dict = get_tables()
    table_names = [k for k in table_dict]
    table_names.sort()
    tables: list[Table] = []
    for table_name in table_names:
        table = table_dict[table_name]
        tables.append(table)
    actual = render.render_tables(tables)
    Path(__file__).parent.joinpath("render_tables.actual").write_text(actual)
    expected = Path(__file__).parent.joinpath("render_tables.expected").read_text()
    assert actual == expected


def test_render_views():
    view_dict = get_views()
    view_names = [k for k in view_dict]
    view_names.sort()
    views: list[View] = []
    for view_name in view_names:
        view = view_dict[view_name]
        views.append(view)
    actual = render.render_views(views)
    Path(__file__).parent.joinpath("render_views.actual").write_text(actual)
    expected = Path(__file__).parent.joinpath("render_views.expected").read_text()
    assert actual == expected


def test_render_procedures():
    procedure_dict = get_procedures()
    procedure_names = [k for k in procedure_dict]
    procedure_names.sort()
    procedures: list[Procedure] = []
    for procedure_name in procedure_names:
        procedure = procedure_dict[procedure_name]
        procedures.append(procedure)
    actual = render.render_procedures(procedures)
    Path(__file__).parent.joinpath("render_procedures.actual").write_text(actual)
    expected = Path(__file__).parent.joinpath("render_procedures.expected").read_text()
    assert actual == expected
