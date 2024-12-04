import sys
import tempfile
from collections.abc import Generator, Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from testcontainers.postgres import PostgresContainer  # type: ignore

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

    engine = create_engine(postgres_container.get_connection_url())
    config.attributes["connection"] = engine

    return config


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
    engine = create_engine(postgres_container.get_connection_url())
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS ai CASCADE;"))
        conn.commit()

    yield engine

    drop_vectorizer_if_exists(1, engine)
    drop_vectorizer_if_exists(2, engine)
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        conn.commit()


def cleanup_model_modules():
    """Clean up any previously imported model modules"""
    # Remove all modules that start with 'models.'
    for module_name in list(sys.modules.keys()):
        if module_name.startswith("models."):
            del sys.modules[module_name]
    # Also remove the parent 'models' module if it exists
    if "models" in sys.modules:
        del sys.modules["models"]


@pytest.fixture
def cleanup_modules():
    yield
    cleanup_model_modules()
