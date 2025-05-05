from pathlib import Path

import psycopg

import pgai
import pgai.semantic_catalog as sc
import pgai.semantic_catalog.file as file
from tests.semantic_catalog.utils import PostgresContainer

DATABASE = "sc_04"
TARGET = "postgres_air"


async def test_import_export(container: PostgresContainer):
    expected = Path(__file__).parent.joinpath("data", "export_yaml.expected")
    actual = Path(__file__).parent.joinpath("data", "export_yaml.actual")

    container.drop_database(DATABASE)
    container.create_database(DATABASE)
    pgai.install(container.connection_string(database=DATABASE))

    async with (
        await psycopg.AsyncConnection.connect(
            container.connection_string(database=DATABASE)
        ) as ccon,
        await psycopg.AsyncConnection.connect(
            container.connection_string(database=TARGET)
        ) as tcon,
    ):
        catalog = await sc.create(ccon)
        with expected.open(mode="r") as r:
            await file.save_to_catalog(ccon, tcon, catalog.id, file.import_from_yaml(r))

        with actual.open(mode="w") as w:
            await file.async_export_to_yaml(w, file.load_from_catalog(ccon, catalog.id))

    expected_yaml = expected.read_text()
    actual_yaml = actual.read_text()
    assert actual_yaml == expected_yaml
