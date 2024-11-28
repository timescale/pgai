from datetime import timedelta
from pathlib import Path

from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

from pgai.configuration import DiskANNIndexingConfig
from pgai.vectorizer import Vectorizer
from pgai.vectorizer.indexing import DiskANNIndexing
from pgai.vectorizer.scheduling import TimescaleScheduling
from tests.vectorizer.extensions.conftest import load_template


def create_migration_script(migrations_dir: Path) -> None:
    """Create a basic migration script"""
    versions_dir = migrations_dir / "versions"
    migration_content = load_template(
        "migrations/001_create_test_table.py.template",
        revision_id="001",
        revises="",
        create_date="2024-03-19 10:00:00.000000",
        down_revision="None",
    )

    with open(versions_dir / "001_create_test_table.py", "w") as f:
        f.write(migration_content)


def create_vectorizer_migration_scripts(migrations_dir: Path) -> None:
    """Create migration scripts for vectorizer testing"""
    versions_dir = migrations_dir / "versions"

    # First migration - create blog table
    blog_content = load_template(
        "migrations/001_create_blog_table.py.template",
        revision_id="001",
        revises="",
        create_date="2024-03-19 10:00:00.000000",
        down_revision="None",
    )
    with open(versions_dir / "001_create_blog_table.py", "w") as f:
        f.write(blog_content)

    # Second migration - create vectorizer
    vectorizer_content = load_template(
        "migrations/002_create_vectorizer.py.template",
        revision_id="002",
        revises="001",
        create_date="2024-03-19 10:01:00.000000",
        down_revision="001",
    )
    with open(versions_dir / "002_create_vectorizer.py", "w") as f:
        f.write(vectorizer_content)


def test_basic_alembic_migration(alembic_config: Config, initialized_engine: Engine):
    """Verify basic Alembic functionality works before testing vectorizer operations"""
    migrations_dir = Path(alembic_config.get_main_option("script_location"))  # type: ignore
    create_migration_script(migrations_dir)

    # Run upgrade
    upgrade(alembic_config, "head")

    # Verify table exists
    inspector = inspect(initialized_engine)
    tables = inspector.get_table_names()
    assert "test_table" in tables

    # Check table structure
    columns = {
        col["name"]: col["type"].__class__.__name__
        for col in inspector.get_columns("test_table")
    }
    assert columns["id"] == "INTEGER"
    assert columns["name"] == "VARCHAR"

    # Run downgrade
    downgrade(alembic_config, "base")

    # Verify table is gone
    inspector = inspect(initialized_engine)
    tables = inspector.get_table_names()
    assert "test_table" not in tables


def test_vectorizer_migration(
    alembic_config: Config,
    initialized_engine: Engine,
    cleanup_modules: None,  # noqa: ARG001
):
    """Test vectorizer creation and deletion via Alembic migrations"""
    migrations_dir = Path(alembic_config.get_main_option("script_location"))  # type: ignore
    create_vectorizer_migration_scripts(migrations_dir)

    # Run upgrade to first migration (create blog table)
    upgrade(alembic_config, "001")

    # Verify blog table exists
    inspector = inspect(initialized_engine)
    tables = inspector.get_table_names()
    assert "blog" in tables

    # Run upgrade to second migration (create vectorizer)
    upgrade(alembic_config, "002")

    # Verify vectorizer exists
    with initialized_engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM ai.vectorizer_status")).fetchone()
        assert result is not None
        assert result.source_table == "public.blog"
        assert result.pending_items == 0  # Since table is empty

    # Run downgrade of vectorizer
    downgrade(alembic_config, "001")

    # Verify vectorizer is gone but blog table remains
    with initialized_engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM ai.vectorizer_status")).fetchall()
        assert len(result) == 0

    inspector = inspect(initialized_engine)
    tables = inspector.get_table_names()
    assert "blog" in tables

    # Run final downgrade
    downgrade(alembic_config, "base")

    # Verify everything is gone
    inspector = inspect(initialized_engine)
    tables = inspector.get_table_names()
    assert "blog" not in tables
    


def test_vectorizer_migration_all_fields(
    alembic_config: Config,
    initialized_engine: Engine,
    cleanup_modules: None,  # noqa: ARG001
):
    """Test vectorizer creation with a bunch of fields"""
    migrations_dir = Path(alembic_config.get_main_option("script_location"))  # type: ignore
    versions_dir = migrations_dir / "versions"

    with initialized_engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE schema timescale;
                CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
                """
            )
        )
        conn.commit()

    # First migration - create blog table
    indexing_config = DiskANNIndexingConfig(
        min_rows=10,
        storage_layout='plain',
        num_neighbors=5,
        search_list_size=10,
        max_alpha=0.5,
        num_dimensions=10,
        num_bits_per_dimension=10,
        create_when_queue_empty=False
    )
    blog_content = load_template(
        "migrations/001_create_blog_table.py.template",
        revision_id="001",
        revises="",
        create_date="2024-03-19 10:00:00.000000",
        down_revision="None",
    )
    with open(versions_dir / "001_create_blog_table.py", "w") as f:
        f.write(blog_content)

    # Second migration - create vectorizer
    vectorizer_content = load_template(
        "migrations/002_create_vectorizer_all_fields.py.template",
        revision_id="002",
        revises="001",
        create_date="2024-03-19 10:01:00.000000",
        down_revision="001",
        indexing=indexing_config.to_python_arg()
    )
    with open(versions_dir / "002_create_vectorizer.py", "w") as f:
        f.write(vectorizer_content)

    # Run upgrade
    upgrade(alembic_config, "head")
    
    # Verify vectorizer exists
    with initialized_engine.connect() as conn:
        rows = conn.execute(
            text("""
                    select pg_catalog.to_jsonb(v) as vectorizer from ai.vectorizer v
                """)
        ).fetchall()
        assert len(rows) == 1
        parsed_vectorizer = Vectorizer.model_validate(rows[0].vectorizer) # type: ignore
        assert parsed_vectorizer.target_table == "blog_posts_embedding"
        assert isinstance(parsed_vectorizer.config.scheduling, TimescaleScheduling)
        assert parsed_vectorizer.config.scheduling.fixed_schedule == True
        assert parsed_vectorizer.config.scheduling.schedule_interval == timedelta(hours=1)
        
        assert isinstance(parsed_vectorizer.config.indexing, DiskANNIndexing)
        assert parsed_vectorizer.config.indexing.min_rows == 10
        assert parsed_vectorizer.config.indexing.storage_layout == 'plain'