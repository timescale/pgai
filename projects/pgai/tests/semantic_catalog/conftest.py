import os
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

from .utils import PostgresContainer

load_dotenv()


def load_postgres_air(container: PostgresContainer):
    script1 = Path(__file__).parent.joinpath("data", "postgres_air.sql").read_text()
    script2 = (
        Path(__file__).parent.joinpath("data", "postgres_air_extra.sql").read_text()
    )
    with (
        psycopg.connect(container.connection_string(database="postgres_air")) as con,
        con.transaction() as _,
        con.cursor() as cur,
    ):
        cur.execute(script1)  # pyright: ignore [reportArgumentType]
        cur.execute(script2)  # pyright: ignore [reportArgumentType]


@pytest.fixture(scope="session")
def container():
    dont_kill_container = os.getenv("DONT_KILL_CONTAINER") is not None
    container = PostgresContainer.get_or_create()
    container.drop_database("postgres_air")
    container.create_database("postgres_air")
    load_postgres_air(container)
    yield container
    if not dont_kill_container:
        container.container.stop()
        container.container.remove()
