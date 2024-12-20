from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from testcontainers.postgres import PostgresContainer  # type: ignore

# Get the path to the fixtures directory relative to this file
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def drop_vectorizer_if_exists(id: int, engine: Engine):
    with engine.connect() as conn:
        vectorizer_exists = conn.execute(
            text(f"SELECT EXISTS (SELECT 1 FROM ai.vectorizer WHERE id = {id})")
        ).scalar()

        if vectorizer_exists:
            conn.execute(text(f"SELECT ai.drop_vectorizer({id}, drop_all=>true);"))
        conn.commit()


@pytest.fixture
def initialized_engine(
    postgres_container: PostgresContainer,
) -> Generator[Engine, None, None]:
    """Create a SQLAlchemy engine with the AI extension enabled.

    Args:
        postgres_container: Postgres test container fixture

    Returns:
        Engine: Configured SQLAlchemy engine
    """
    engine = create_engine(postgres_container.get_connection_url(driver="psycopg"))
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS ai CASCADE;"))
        conn.commit()

    yield engine

    drop_vectorizer_if_exists(1, engine)
    drop_vectorizer_if_exists(2, engine)
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        conn.commit()
