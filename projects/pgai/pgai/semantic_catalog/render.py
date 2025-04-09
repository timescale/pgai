from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from pgai.semantic_catalog.models import Table, View, Proc

template_dir = Path(__file__).parent.joinpath("templates")
env = Environment(loader=FileSystemLoader(template_dir))


def render_table(table: Table) -> str:
    template = env.get_template("table.j2")
    return template.render(table=table)


def render_view(view: View) -> str:
    template = env.get_template("view.j2")
    return template.render(view=view)


def render_proc(proc: Proc) -> str:
    template = env.get_template("proc.j2")
    return template.render(proc=proc)
