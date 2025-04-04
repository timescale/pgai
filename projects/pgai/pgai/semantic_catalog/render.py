from pathlib import Path

import psycopg
from jinja2 import Environment, FileSystemLoader
from psycopg.sql import SQL, Identifier, Literal

from pgai.semantic_catalog.models import (
    Fact,
    ObjectDescription,
    Procedure,
    SQLExample,
    Table,
    View,
)

template_dir = Path(__file__).parent.joinpath("templates")
env = Environment(loader=FileSystemLoader(template_dir))


def render_table(table: Table) -> str:
    template = env.get_template("table.j2")
    return template.render(table=table)


def render_tables(tables: list[Table]) -> str:
    return "\n\n".join(map(render_table, tables)).strip()


def render_view(view: View) -> str:
    template = env.get_template("view.j2")
    return template.render(view=view)


def render_views(views: list[View]) -> str:
    return "\n\n".join(map(render_view, views)).strip()


def render_procedure(proc: Procedure) -> str:
    template = env.get_template("procedure.j2")
    return template.render(proc=proc)


def render_procedures(procedures: list[Procedure]) -> str:
    return "\n\n".join(map(render_procedure, procedures)).strip()


def render_objects(objects: list[Table | View | Procedure]) -> str:
    output = ""
    for obj in objects:
        match obj:
            case Table():
                output += render_table(obj)
            case View():
                output += render_view(obj)
            case Procedure():
                output += render_procedure(obj)
        output += "\n\n"
    return output.rstrip()


def render_fact(fact: Fact) -> str:
    template = env.get_template("fact.j2")
    return template.render(fact=fact)


def render_sql_example(example: SQLExample) -> str:
    template = env.get_template("sql_example.j2")
    return template.render(example=example)


def render_description_to_sql(
    con: psycopg.AsyncConnection, catalog_name: str, description: ObjectDescription
) -> str:
    match description.objtype:
        case "table":
            assert len(description.objnames) == 2
            return (
                SQL("select ai.sc_set_table_desc({}, {}, {}, {}, {}, {});\n")
                .format(
                    Literal(description.classid),
                    Literal(description.objid),
                    Literal(description.objnames[0]),
                    Literal(description.objnames[1]),
                    Literal(description.description),
                    Literal(catalog_name),
                )
                .as_string(con)
            )
        case "view":
            assert len(description.objnames) == 2
            return (
                SQL("select ai.sc_set_view_desc({}, {}, {}, {}, {}, {});\n")
                .format(
                    Literal(description.classid),
                    Literal(description.objid),
                    Literal(description.objnames[0]),
                    Literal(description.objnames[1]),
                    Literal(description.description),
                    Literal(catalog_name),
                )
                .as_string(con)
            )
        case "table column":
            assert len(description.objnames) == 3
            return (
                SQL(
                    "select ai.sc_set_table_col_desc({}, {}, {}, {}, {}, {}, {}, {});\n"
                )  # noqa
                .format(
                    Literal(description.classid),
                    Literal(description.objid),
                    Literal(description.objsubid),
                    Literal(description.objnames[0]),
                    Literal(description.objnames[1]),
                    Literal(description.objnames[2]),
                    Literal(description.description),
                    Literal(catalog_name),
                )
                .as_string(con)
            )
        case "view column":
            assert len(description.objnames) == 3
            return (
                SQL("select ai.sc_set_view_col_desc({}, {}, {}, {}, {}, {}, {}, {});\n")  # noqa
                .format(
                    Literal(description.classid),
                    Literal(description.objid),
                    Literal(description.objsubid),
                    Literal(description.objnames[0]),
                    Literal(description.objnames[1]),
                    Literal(description.objnames[2]),
                    Literal(description.description),
                    Literal(catalog_name),
                )
                .as_string(con)
            )
        case "procedure":
            assert len(description.objnames) >= 2
            return (
                SQL("select ai.sc_set_proc_desc({}, {}, {}, {}, {}, {}, {});\n")
                .format(
                    Literal(description.classid),
                    Literal(description.objid),
                    Literal(description.objnames[0]),
                    Literal(description.objnames[1]),
                    Literal(description.objargs),
                    Literal(description.description),
                    Literal(catalog_name),
                )
                .as_string(con)
            )
        case "function":
            assert len(description.objnames) >= 2
            return (
                SQL("select ai.sc_set_func_desc({}, {}, {}, {}, {}, {}, {});\n")
                .format(
                    Literal(description.classid),
                    Literal(description.objid),
                    Literal(description.objnames[0]),
                    Literal(description.objnames[1]),
                    Literal(description.objargs),
                    Literal(description.description),
                    Literal(catalog_name),
                )
                .as_string(con)
            )
        case "aggregate":
            assert len(description.objnames) >= 2
            return (
                SQL("select ai.sc_set_agg_desc({}, {}, {}, {}, {}, {}, {});\n")
                .format(
                    Literal(description.classid),
                    Literal(description.objid),
                    Literal(description.objnames[0]),
                    Literal(description.objnames[1]),
                    Literal(description.objargs),
                    Literal(description.description),
                    Literal(catalog_name),
                )
                .as_string(con)
            )
        case _:
            raise ValueError(f"unknown description objtype: {description.objtype}")


def render_description_to_comment(
    con: psycopg.AsyncConnection, description: ObjectDescription
) -> str:
    match description.objtype:
        case "table" | "view":
            assert len(description.objnames) >= 2
            type = SQL("TABLE") if description.objtype == "table" else SQL("VIEW")
            return (
                SQL("COMMENT ON {} {}.{} IS {};\n")
                .format(
                    type,
                    Identifier(description.objnames[0]),
                    Identifier(description.objnames[1]),
                    Literal(description.description),
                )
                .as_string(con)
            )
        case "table column" | "view column":
            assert len(description.objnames) == 3
            return (
                SQL("COMMENT ON COLUMN {}.{}.{} IS {};\n")
                .format(
                    Identifier(description.objnames[0]),
                    Identifier(description.objnames[1]),
                    Identifier(description.objnames[2]),
                    Literal(description.description),
                )
                .as_string(con)
            )
        case "procedure" | "function" | "aggregate":
            assert len(description.objnames) >= 2
            type = {
                "procedure": SQL("PROCEDURE"),
                "function": SQL("FUNCTION"),
                "aggregate": SQL("AGGREGATE"),
            }[description.objtype]
            return (
                SQL("COMMENT ON {} {}.{}({}) IS {};\n")
                .format(
                    type,
                    Identifier(description.objnames[0]),
                    Identifier(description.objnames[1]),
                    SQL(", ".join(arg for arg in description.objargs)),  # pyright: ignore [reportArgumentType]
                    Literal(description.description),
                )
                .as_string(con)
            )
        case _:
            raise ValueError(f"unknown description objtype: {description.objtype}")
