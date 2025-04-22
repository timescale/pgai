from pathlib import Path

import psycopg

from pgai.semantic_catalog.sample import sample_table, sample_view
from tests.semantic_catalog.utils import PostgresContainer


async def load_airports(con: psycopg.AsyncConnection) -> None:
    airport_data = Path(__file__).parent.joinpath("data", "airport.sql").read_text()
    async with (
        con.cursor() as cur,
        cur.copy("copy postgres_air.airport from stdin with (format csv)") as cpy,
    ):
        await cpy.write(airport_data)


async def test_sample_table(container: PostgresContainer) -> None:
    async with (
        await psycopg.AsyncConnection.connect(
            container.connection_string(database="postgres_air")
        ) as con,
        con.transaction(force_rollback=True) as _,
    ):
        await load_airports(con)
        actual = await sample_table(con, "postgres_air", "airport")
    Path(__file__).parent.joinpath("data", "table_sample.actual").write_text(actual)
    expected = (
        Path(__file__).parent.joinpath("data", "table_sample.expected").read_text()
    )
    assert actual == expected


async def test_sample_view(container: PostgresContainer) -> None:
    async with (
        await psycopg.AsyncConnection.connect(
            container.connection_string(database="postgres_air")
        ) as con,
        con.transaction(force_rollback=True) as _,
    ):
        await load_airports(con)
        async with con.cursor() as cur:
            await cur.execute(
                "create view public.airport as select * from postgres_air.airport"
            )
        actual = await sample_view(con, "public", "airport")
    Path(__file__).parent.joinpath("data", "view_sample.actual").write_text(actual)
    expected = (
        Path(__file__).parent.joinpath("data", "view_sample.expected").read_text()
    )
    assert actual == expected
