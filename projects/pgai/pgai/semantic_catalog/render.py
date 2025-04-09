from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from pgai.semantic_catalog.models import Procedure, Table, View

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
