from pathlib import Path

import psycopg
from psycopg.sql import SQL, Identifier

import pgai
from tests.semantic_catalog.utils import (
    PostgresContainer,
    get_procedures,
    get_tables,
    get_views,
)


async def test_desc_injest(container: PostgresContainer):
    database = "test_desc_injest"
    container.drop_database(database)
    container.create_database(database)
    expected: set[str] = set()
    for table in get_tables():
        expected.add(f"{table.schema_name}.{table.table_name}")
        if table.columns:
            for column in table.columns:
                expected.add(f"{table.schema_name}.{table.table_name}.{column.name}")
    for view in get_views():
        expected.add(f"{view.schema_name}.{view.view_name}")
        if view.columns:
            for column in view.columns:
                expected.add(f"{view.schema_name}.{view.view_name}.{column.name}")
    for proc in get_procedures():
        expected.add(f"{proc.schema_name}.{proc.proc_name}")
    script = (
        Path(__file__)
        .parent.joinpath("data", "render_description_to_sql.expected")
        .read_text()
    )
    connection_str = container.connection_string(database=database)
    pgai.install(connection_str)
    async with await psycopg.AsyncConnection.connect(connection_str) as con:  # noqa SIM117
        async with con.cursor() as cur:
            await cur.execute("select ai.create_semantic_catalog('my_catalog')")
            row = await cur.fetchone()
            if row is None:
                raise RuntimeError("Failed to create catalog")
            catalog_id: int = int(row[0])
            await con.commit()
            for line in script.split("\n"):
                await cur.execute(line)  # pyright: ignore [reportArgumentType]
                await con.commit()
            query = SQL("""\
                select array_to_string(x.objnames, '.')
                from ai.{} x
            """).format(Identifier(f"semantic_catalog_obj_{catalog_id}"))
            await cur.execute(query)
            actual: set[str] = set()
            async for row in cur:
                actual.add(row[0])
    assert actual == expected
