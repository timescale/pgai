from pathlib import Path

from pgai.semantic_catalog import render

from .utils import get_procedures, get_tables, get_views


def test_render_tables():
    tables = get_tables()
    for table in tables:
        table.id = 0
    actual = render.render_tables(tables)
    Path(__file__).parent.joinpath("data", "render_tables.actual").write_text(actual)
    expected = (
        Path(__file__).parent.joinpath("data", "render_tables.expected").read_text()
    )
    assert actual == expected


def test_render_views():
    views = get_views()
    for view in views:
        view.id = 0
    actual = render.render_views(views)
    Path(__file__).parent.joinpath("data", "render_views.actual").write_text(actual)
    expected = (
        Path(__file__).parent.joinpath("data", "render_views.expected").read_text()
    )
    assert actual == expected


def test_render_procedures():
    procedures = get_procedures()
    for procedure in procedures:
        procedure.id = 0
    actual = render.render_procedures(procedures)
    Path(__file__).parent.joinpath("data", "render_procedures.actual").write_text(
        actual
    )
    expected = (
        Path(__file__).parent.joinpath("data", "render_procedures.expected").read_text()
    )
    assert actual == expected
