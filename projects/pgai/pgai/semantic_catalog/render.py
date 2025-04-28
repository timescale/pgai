from collections.abc import Iterable

# from jinja2 import Environment, FileSystemLoader
from pgai.semantic_catalog.models import (
    Fact,
    Procedure,
    SQLExample,
    Table,
    View,
)
from pgai.semantic_catalog.templates import env

# template_dir = Path(__file__).parent.joinpath("templates")
# env = Environment(loader=FileSystemLoader(template_dir))


def render_table(table: Table) -> str:
    template = env.get_template("table.j2")
    return template.render(table=table)


def render_tables(tables: Iterable[Table]) -> str:
    return "\n\n".join(map(render_table, tables)).strip()


def render_view(view: View) -> str:
    template = env.get_template("view.j2")
    return template.render(view=view)


def render_views(views: Iterable[View]) -> str:
    return "\n\n".join(map(render_view, views)).strip()


def render_procedure(proc: Procedure) -> str:
    template = env.get_template("procedure.j2")
    return template.render(proc=proc)


def render_procedures(procedures: Iterable[Procedure]) -> str:
    return "\n\n".join(map(render_procedure, procedures)).strip()


def render_object(object: Table | View | Procedure) -> str:
    match object:
        case Table():
            return render_table(object)
        case View():
            return render_view(object)
        case Procedure():
            return render_procedure(object)


def render_objects(objects: Iterable[Table | View | Procedure]) -> str:
    return "\n\n".join(map(render_object, objects)).strip()


def render_fact(fact: Fact) -> str:
    template = env.get_template("fact.j2")
    return template.render(fact=fact)


def render_facts(facts: Iterable[Fact]) -> str:
    return "\n\n".join(map(render_fact, facts)).strip()


def render_sql_example(example: SQLExample) -> str:
    template = env.get_template("sql_example.j2")
    return template.render(example=example)


def render_sql_examples(examples: Iterable[SQLExample]) -> str:
    return "\n\n".join(map(render_sql_example, examples)).strip()
