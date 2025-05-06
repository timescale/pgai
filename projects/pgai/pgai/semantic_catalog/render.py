from collections.abc import Iterable

from pgai.semantic_catalog.models import (
    Fact,
    Procedure,
    SQLExample,
    Table,
    View,
)
from pgai.semantic_catalog.templates import env


def render_table(table: Table) -> str:
    """Render a table object using the table template.

    Args:
        table: The Table object to render.

    Returns:
        The rendered table as a string.
    """
    template = env.get_template("table.j2")
    return template.render(table=table)


def render_tables(tables: Iterable[Table]) -> str:
    """Render multiple table objects.

    Args:
        tables: An iterable of Table objects to render.

    Returns:
        A string containing all rendered tables separated by newlines.
    """
    return "\n".join(map(render_table, tables)).strip()


def render_view(view: View) -> str:
    """Render a view object using the view template.

    Args:
        view: The View object to render.

    Returns:
        The rendered view as a string.
    """
    template = env.get_template("view.j2")
    return template.render(view=view)


def render_views(views: Iterable[View]) -> str:
    """Render multiple view objects.

    Args:
        views: An iterable of View objects to render.

    Returns:
        A string containing all rendered views separated by newlines.
    """
    return "\n".join(map(render_view, views)).strip()


def render_procedure(proc: Procedure) -> str:
    """Render a procedure object using the procedure template.

    Args:
        proc: The Procedure object to render.

    Returns:
        The rendered procedure as a string.
    """
    template = env.get_template("procedure.j2")
    return template.render(proc=proc)


def render_procedures(procedures: Iterable[Procedure]) -> str:
    """Render multiple procedure objects.

    Args:
        procedures: An iterable of Procedure objects to render.

    Returns:
        A string containing all rendered procedures separated by newlines.
    """
    return "\n".join(map(render_procedure, procedures)).strip()


def render_object(object: Table | View | Procedure) -> str:
    """Render a database object based on its type.

    Args:
        object: A database object (Table, View, or Procedure) to render.

    Returns:
        The rendered object as a string.
    """
    match object:
        case Table():
            return render_table(object)
        case View():
            return render_view(object)
        case Procedure():
            return render_procedure(object)


def render_objects(objects: Iterable[Table | View | Procedure]) -> str:
    """Render multiple database objects of various types.

    Args:
        objects: An iterable of database objects (Tables, Views, or Procedures) to render.

    Returns:
        A string containing all rendered objects separated by newlines.
    """  # noqa: E501
    return "\n".join(map(render_object, objects)).strip()


def render_fact(fact: Fact) -> str:
    """Render a fact object using the fact template.

    Args:
        fact: The Fact object to render.

    Returns:
        The rendered fact as a string.
    """
    template = env.get_template("fact.j2")
    return template.render(fact=fact)


def render_facts(facts: Iterable[Fact]) -> str:
    """Render multiple fact objects.

    Args:
        facts: An iterable of Fact objects to render.

    Returns:
        A string containing all rendered facts separated by newlines.
    """
    return "\n".join(map(render_fact, facts)).strip()


def render_sql_example(example: SQLExample) -> str:
    """Render a SQL example object using the sql_example template.

    Args:
        example: The SQLExample object to render.

    Returns:
        The rendered SQL example as a string.
    """
    template = env.get_template("sql_example.j2")
    return template.render(example=example)


def render_sql_examples(examples: Iterable[SQLExample]) -> str:
    """Render multiple SQL example objects.

    Args:
        examples: An iterable of SQLExample objects to render.

    Returns:
        A string containing all rendered SQL examples separated by newlines.
    """
    return "\n".join(map(render_sql_example, examples)).strip()
