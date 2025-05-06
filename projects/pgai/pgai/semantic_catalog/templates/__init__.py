"""Templates module for the semantic catalog.

This module provides a Jinja2 environment and templates for rendering database objects
(tables, views, procedures), SQL examples, facts, and prompts for SQL generation.
The templates are used to format the catalog items for display, export, and AI
interaction.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

# Create a Jinja2 environment with the templates directory as the loader path
env = Environment(loader=FileSystemLoader(Path(__file__).parent.joinpath("templates")))
