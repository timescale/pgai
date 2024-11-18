import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, Engine, text
from testcontainers.postgres import PostgresContainer

# Get the path to the fixtures directory relative to this file
FIXTURES_DIR = Path(__file__).parent / "fixtures"

def load_template(template_path: str, **kwargs: dict[str,str]) -> str:
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
    ini_content = load_template("alembic/alembic.ini.template")
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
    config.set_main_option("sqlalchemy.url", postgres_container.get_connection_url())

    engine = create_engine(postgres_container.get_connection_url())
    config.attributes["connection"] = engine

    return config


@pytest.fixture
def initialized_engine(postgres_container: PostgresContainer) -> Engine:
    """Create a SQLAlchemy engine with the AI extension enabled.

    Args:
        postgres_container: Postgres test container fixture

    Returns:
        Engine: Configured SQLAlchemy engine
    """
    engine = create_engine(postgres_container.get_connection_url())
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS ai CASCADE;"))
        conn.commit()
    return engine