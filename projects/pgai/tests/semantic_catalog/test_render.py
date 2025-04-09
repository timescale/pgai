from pathlib import Path

from pgai.semantic_catalog import render
from pgai.semantic_catalog.models import Table, View, Procedure
from .utils import get_tables, get_views, get_procedures


def test_render_tables():
    table_dict = get_tables()
    table_names = [k for k in table_dict.keys()]
    table_names.sort()
    tables: list[Table] = []
    for i, table_name in enumerate(table_names):
        table = table_dict[table_name]
        table.id = i
        tables.append(table)
    actual = render.render_tables(tables)
    expected = Path(__file__).parent.joinpath('render_tables.expected').read_text()
    assert actual == expected


def test_render_views():
    view_dict = get_views()
    view_names = [k for k in view_dict.keys()]
    view_names.sort()
    views: list[View] = []
    for i, view_name in enumerate(view_names):
        view = view_dict[view_name]
        view.id = i
        views.append(view)
    actual = render.render_views(views)
    expected = Path(__file__).parent.joinpath('render_views.expected').read_text()
    assert actual == expected


def test_render_procedures():
    procedure_dict = get_procedures()
    procedure_names = [k for k in procedure_dict.keys()]
    procedure_names.sort()
    procedures: list[Procedure] = []
    for i, procedure_name in enumerate(procedure_names):
        procedure = procedure_dict[procedure_name]
        procedure.id = i
        procedures.append(procedure)
    actual = render.render_procedures(procedures)
    expected = Path(__file__).parent.joinpath('render_procedures.expected').read_text()
    assert actual == expected
