import tempfile
from collections.abc import Generator, Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from testcontainers.postgres import PostgresContainer  # type: ignore

import pgai

# Get the path to the fixtures directory relative to this file
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_template(template_path: str, **kwargs: str | int) -> str:
    """Load a template file and substitute any provided values.

    Args:
        template_path: Path relative to fixtures directory
        **kwargs: Key-value pairs to substitute in template

    Returns:
        str: Processed template content
    """
    template_file = FIXTURES_DIR / template_path
    with open(template_file) as f:
        content = f.read()

    return content.format(**kwargs) if kwargs else content


@pytest.fixture
def alembic_dir() -> Iterator[Path]:
    """Create and manage a temporary directory for Alembic migrations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        migrations_dir = temp_path / "migrations"
        versions_dir = migrations_dir / "versions"

        # Create directory structure
        migrations_dir.mkdir()
        versions_dir.mkdir()

        # Copy script.py.mako template
        script_content = load_template("alembic/script.py.mako")
        with open(migrations_dir / "script.py.mako", "w") as f:
            f.write(script_content)

        yield temp_path


@pytest.fixture
def alembic_config(alembic_dir: Path, postgres_container: PostgresContainer) -> Config:
    """Create a configured Alembic environment."""
    # Create alembic.ini from template
    ini_path = alembic_dir / "alembic.ini"
    ini_content = load_template(
        "alembic/alembic.ini.template",
        sqlalchemy_url=postgres_container.get_connection_url(),
    )
    with open(ini_path, "w") as f:
        f.write(ini_content)

    # Create env.py from template
    env_path = alembic_dir / "migrations" / "env.py"
    env_content = load_template("alembic/env.py.template")
    with open(env_path, "w") as f:
        f.write(env_content)

    # Configure and return
    config = Config(ini_path)
    config.set_main_option("script_location", str(alembic_dir / "migrations"))

    engine = create_engine(postgres_container.get_connection_url(driver="psycopg"))
    config.attributes["connection"] = engine

    return config


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
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb;"))
        conn.commit()

    pgai.install(postgres_container.get_connection_url())

    yield engine

    with engine.connect() as conn:
        # alembic somehow seems to leave some connections open
        # which leads to deadlocks, this cleans those up
        conn.execute(
            text("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE pid <> pg_backend_pid()
                AND datname = current_database();
            """)
        )
        conn.execute(text("DROP SCHEMA public cascade;"))
        conn.commit()
        conn.execute(text("CREATE SCHEMA public;"))
        conn.commit()
        conn.execute(text("DROP SCHEMA ai cascade;"))
        conn.commit()
