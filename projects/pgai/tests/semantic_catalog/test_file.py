from pathlib import Path

import psycopg

import pgai
import pgai.semantic_catalog as sc
import pgai.semantic_catalog.file as file
from tests.semantic_catalog.utils import PostgresContainer

DATABASE = "sc_04"
TARGET = "postgres_air"


async def test_import_export(container: PostgresContainer):
    initial = Path(__file__).parent.joinpath("data", "catalog.yaml")
    export1 = Path(__file__).parent.joinpath("data", "export1.yaml")
    export2 = Path(__file__).parent.joinpath("data", "export2.yaml")

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

        # load from an initial yaml file
        with initial.open(mode="r") as r:
            await file.save_to_catalog(ccon, tcon, catalog.id, file.import_from_yaml(r))

        # export the catalog to a yaml file. this will include ids
        with export1.open(mode="w") as w:
            await file.async_export_to_yaml(w, file.load_from_catalog(ccon, catalog.id))

        # import this yaml to the catalog (should not change anything)
        with export1.open(mode="r") as r:
            await file.save_to_catalog(ccon, tcon, catalog.id, file.import_from_yaml(r))

        # do it again for good measure
        with export1.open(mode="r") as r:
            await file.save_to_catalog(ccon, tcon, catalog.id, file.import_from_yaml(r))

        # export to another file
        with export2.open(mode="w") as w:
            await file.async_export_to_yaml(w, file.load_from_catalog(ccon, catalog.id))

    export1_yaml = export1.read_text()
    export2_yaml = export2.read_text()
    assert export2_yaml == export1_yaml
