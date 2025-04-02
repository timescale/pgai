"""
The migration template for these tests lies in
fixtures/migrations/generic_vectorizer.py.template
Each test generates a different migration, runs it, and verifies the configuration
This doesn't test if the vectorizer behaves as expected,
but it validates that the create_vectorizer call works.

If you add new configuration options, add a test for them here.
Either in an existing test case or a new one.
The config classes for migrations lie in pgai/alembic/configuration.py
If the migration and the validation definitions overlap,
it is possible to define a parent class in base.py
see e.g. CharacterTextSplitterConfig as an example
"""

import textwrap
from datetime import timedelta
from pathlib import Path
from typing import Any

from alembic.command import downgrade, upgrade
from alembic.config import Config
from sqlalchemy import Engine, text

from pgai.vectorizer.configuration import (
    ChunkingCharacterTextSplitterConfig,
    ChunkingRecursiveCharacterTextSplitterConfig,
    EmbeddingOllamaConfig,
    EmbeddingOpenaiConfig,
    EmbeddingVoyageaiConfig,
    FormattingPythonTemplateConfig,
    IndexingHnswConfig,
    LoadingColumnConfig,
    ProcessingDefaultConfig,
    SchedulingTimescaledbConfig,
)
from tests.vectorizer.extensions.conftest import load_template


def create_vectorizer_migration(migrations_dir: Path, vectorizer_config: str) -> None:
    """Create migration script with the given vectorizer configuration"""
    versions_dir = migrations_dir / "versions"
    migration_content = load_template(
        "migrations/generic_vectorizer.py.template",
        revision_id="001",
        revises="",
        create_date="2024-03-19 10:00:00.000000",
        down_revision="None",
        vectorizer_config=vectorizer_config,
    )

    with open(versions_dir / "001_generic_vectorizer.py", "w") as f:
        f.write(migration_content)


def create_vectorizer_config_code(**kwargs: Any) -> str:
    """Convert configuration objects to valid Python code for the migration template"""
    return textwrap.dedent(f"""
        op.create_vectorizer(
            source='public.blog',
            **{kwargs}
        )
    """).strip()


def test_openai_vectorizer(
    alembic_config: Config,
    initialized_engine: Engine,
):
    """Test OpenAI vectorizer configuration"""
    config = create_vectorizer_config_code(
        loading=LoadingColumnConfig("content"),
        embedding=EmbeddingOpenaiConfig(
            model="text-embedding-3-small",
            dimensions=768,
            chat_user="test_user",
            api_key_name="TEST_OPENAI_KEY",
        ),
        chunking=ChunkingCharacterTextSplitterConfig(
            chunk_size=256,
            chunk_overlap=20,
            separator="\n",
            is_separator_regex=False,
        ),
    )

    migrations_dir = Path(alembic_config.get_main_option("script_location"))  # type: ignore
    create_vectorizer_migration(migrations_dir, config)

    # Run upgrade
    upgrade(alembic_config, "head")

    # Verify configuration
    with initialized_engine.connect() as conn:
        vectorizer = conn.execute(text("SELECT * FROM ai.vectorizer")).fetchone()
        assert vectorizer is not None
        config = str(dict(vectorizer._mapping))  # type: ignore
        assert "text-embedding-3-small" in config
        assert "768" in config
        assert "test_user" in config

    # Run downgrade
    downgrade(alembic_config, "base")


def test_ollama_vectorizer(
    alembic_config: Config,
    initialized_engine: Engine,
):
    """Test Ollama vectorizer configuration"""
    config = create_vectorizer_config_code(
        loading=LoadingColumnConfig("content"),
        embedding=EmbeddingOllamaConfig(
            model="nomic-embed-text",
            dimensions=768,
            base_url="http://localhost:11434",
            keep_alive="5m",
        ),
        chunking=ChunkingRecursiveCharacterTextSplitterConfig(
            chunk_size=300,
            chunk_overlap=30,
            separators=["\n\n", "\n", "; "],
            is_separator_regex=False,
        ),
        formatting=FormattingPythonTemplateConfig(
            template="Title: $title\nContent: $chunk"
        ),
    )

    migrations_dir = Path(alembic_config.get_main_option("script_location"))  # type: ignore
    create_vectorizer_migration(migrations_dir, config)

    # Run upgrade
    upgrade(alembic_config, "head")

    # Verify configuration
    with initialized_engine.connect() as conn:
        vectorizer = conn.execute(text("SELECT * FROM ai.vectorizer")).fetchone()
        assert vectorizer is not None
        config = str(dict(vectorizer._mapping))  # type: ignore
        assert "nomic-embed-text" in config
        assert "http://localhost:11434" in config

    # Run downgrade
    downgrade(alembic_config, "base")


def test_voyage_vectorizer(
    alembic_config: Config,
    initialized_engine: Engine,
):
    """Test VoyageAI vectorizer configuration"""

    # create the ai extension to test the timescaledb scheduling
    with initialized_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS ai CASCADE;"))
        conn.commit()

    config = create_vectorizer_config_code(
        loading=LoadingColumnConfig("content"),
        embedding=EmbeddingVoyageaiConfig(
            model="voyage-ai-1",
            dimensions=256,
        ),
        chunking=ChunkingRecursiveCharacterTextSplitterConfig(),
        indexing=IndexingHnswConfig(
            min_rows=10000,
            opclass="vector_l1_ops",
            m=32,
            ef_construction=128,
            create_when_queue_empty=True,
        ),
        scheduling=SchedulingTimescaledbConfig(
            schedule_interval=timedelta(minutes=10), timezone="UTC", fixed_schedule=True
        ),
        processing=ProcessingDefaultConfig(batch_size=100, concurrency=2),
    )

    migrations_dir = Path(alembic_config.get_main_option("script_location"))  # type: ignore
    create_vectorizer_migration(migrations_dir, config)

    # Run upgrade
    upgrade(alembic_config, "head")

    # Verify configuration
    with initialized_engine.connect() as conn:
        vectorizer = conn.execute(text("SELECT * FROM ai.vectorizer")).fetchone()
        assert vectorizer is not None
        config = str(dict(vectorizer._mapping))  # type: ignore
        assert "voyage-ai-1" in config
        assert "256" in config
        assert "document" in config
        assert "vector_l1_ops" in config
        assert "32" in config  # m parameter
        assert "128" in config  # ef_construction

    # Run downgrade
    downgrade(alembic_config, "base")


def test_hnsw_vectorizer(
    alembic_config: Config,
    initialized_engine: Engine,
):
    """Test HNSW vectorizer configuration"""

    # create the ai extension to test the timescaledb scheduling
    # (and that's needed for auto indexing)
    with initialized_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS ai CASCADE;"))
        conn.commit()

    config = create_vectorizer_config_code(
        loading=LoadingColumnConfig("content"),
        embedding=EmbeddingOpenaiConfig(
            model="text-embedding-3-small",
            dimensions=768,
            api_key_name="TEST_OPENAI_KEY",
        ),
        chunking=ChunkingCharacterTextSplitterConfig(
            chunk_size=200,
            chunk_overlap=25,
            separator=" ",
            is_separator_regex=False,
        ),
        indexing=IndexingHnswConfig(
            min_rows=50000,
            opclass="vector_l1_ops",
            m=16,
            ef_construction=64,
            create_when_queue_empty=True,
        ),
        scheduling=SchedulingTimescaledbConfig(
            schedule_interval=timedelta(minutes=10), fixed_schedule=False
        ),
    )

    migrations_dir = Path(alembic_config.get_main_option("script_location"))  # type: ignore
    create_vectorizer_migration(migrations_dir, config)

    # Run upgrade
    upgrade(alembic_config, "head")

    # Verify configuration
    with initialized_engine.connect() as conn:
        vectorizer = conn.execute(text("SELECT * FROM ai.vectorizer")).fetchone()
        assert vectorizer is not None
        config = str(dict(vectorizer._mapping))  # type: ignore
        assert "vector_l1_ops" in config
        assert "16" in config  # m parameter
        assert "64" in config  # ef_construction

    # Run downgrade
    downgrade(alembic_config, "base")
