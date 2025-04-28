from pathlib import Path

from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader(Path(__file__).parent.joinpath("templates")))
