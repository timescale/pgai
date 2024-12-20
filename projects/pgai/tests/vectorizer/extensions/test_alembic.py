from pathlib import Path
from typing import Dict, Any
import textwrap
from alembic.command import upgrade, downgrade
from alembic.config import Config
from charset_normalizer.utils import is_separator
from sqlalchemy import Engine, inspect, text

from tests.vectorizer.extensions.conftest import load_template
from pgai.vectorizer.configuration import (
    OpenAIConfig,
    OllamaConfig,
    CharacterTextSplitterConfig,
    RecursiveCharacterTextSplitterConfig,
    HNSWIndexingConfig,
    PythonTemplateConfig,
    TimescaleSchedulingConfig,
    ProcessingConfig,
)
from datetime import timedelta

def create_vectorizer_migration(migrations_dir: Path, vectorizer_config: str) -> None:
    """Create migration script with the given vectorizer configuration"""
    versions_dir = migrations_dir / "versions"
    migration_content = load_template(
        "migrations/generic_vectorizer.py.template",
        revision_id="001",
        revises="",
        create_date="2024-03-19 10:00:00.000000",
        down_revision="None",
        vectorizer_config=vectorizer_config
    )
    
    with open(versions_dir / "001_generic_vectorizer.py", "w") as f:
        f.write(migration_content)

def create_vectorizer_config_code(**kwargs) -> str:
    """Convert configuration objects to valid Python code for the migration template"""
    return textwrap.dedent(f"""
        op.create_vectorizer(
            source_table='public.blog',
            **{kwargs}
        )
    """).strip()

def test_openai_vectorizer(
    alembic_config: Config,
    initialized_engine: Engine,
    cleanup_modules: None,  # noqa: ARG001
):
    """Test OpenAI vectorizer configuration"""
    config = create_vectorizer_config_code(
        embedding=OpenAIConfig(
            model='text-embedding-3-small',
            dimensions=768,
            chat_user='test_user',
            api_key_name='TEST_OPENAI_KEY'
        ),
        chunking=CharacterTextSplitterConfig(
            chunk_column='content',
            chunk_size=256,
            chunk_overlap=20,
            separator='\n',
            is_separator_regex=False,
        )
    )
    
    migrations_dir = Path(alembic_config.get_main_option("script_location"))
    create_vectorizer_migration(migrations_dir, config)
    
    # Run upgrade
    upgrade(alembic_config, "head")
    
    # Verify configuration
    with initialized_engine.connect() as conn:
        vectorizer = conn.execute(text("SELECT * FROM ai.vectorizer")).fetchone()
        assert vectorizer is not None
        config = str(dict(vectorizer._mapping))
        assert "text-embedding-3-small" in config
        assert "768" in config
        assert "test_user" in config
    
    # Run downgrade
    downgrade(alembic_config, "base")

def test_ollama_vectorizer(
    alembic_config: Config,
    initialized_engine: Engine,
    cleanup_modules: None,  # noqa: ARG001
):
    """Test Ollama vectorizer configuration"""
    config = create_vectorizer_config_code(
        embedding=OllamaConfig(
            model='nomic-embed-text',
            dimensions=768,
            base_url='http://localhost:11434',
            keep_alive='5m'
        ),
        chunking=RecursiveCharacterTextSplitterConfig(
            chunk_column='content',
            chunk_size=300,
            chunk_overlap=30,
            separators=['\n\n', '\n', '; '],
            is_separator_regex=False,
        ),
        formatting=PythonTemplateConfig(
            template='Title: $title\nContent: $chunk'
        )
    )
    
    migrations_dir = Path(alembic_config.get_main_option("script_location"))
    create_vectorizer_migration(migrations_dir, config)
    
    # Run upgrade
    upgrade(alembic_config, "head")
    
    # Verify configuration
    with initialized_engine.connect() as conn:
        vectorizer = conn.execute(text("SELECT * FROM ai.vectorizer")).fetchone()
        assert vectorizer is not None
        config = str(dict(vectorizer._mapping))
        assert "nomic-embed-text" in config
        assert "http://localhost:11434" in config
    
    # Run downgrade
    downgrade(alembic_config, "base")

def test_hnsw_vectorizer(
    alembic_config: Config,
    initialized_engine: Engine,
    cleanup_modules: None,  # noqa: ARG001
):
    """Test HNSW vectorizer configuration"""
    config = create_vectorizer_config_code(
        embedding=OpenAIConfig(
            model='text-embedding-3-small',
            dimensions=768,
            api_key_name='TEST_OPENAI_KEY'
        ),
        chunking=CharacterTextSplitterConfig(
            chunk_column='content',
            chunk_size=200,
            chunk_overlap=25,
            separator=' ',
            is_separator_regex=False,
        ),
        indexing=HNSWIndexingConfig(
            min_rows=50000,
            opclass='vector_l1_ops',
            m=16,
            ef_construction=64,
            create_when_queue_empty=True
        ),
        scheduling=TimescaleSchedulingConfig(
            interval=timedelta(minutes=5),
            retention_policy='1d',
            fixed_schedule=False
        )
    )
    
    migrations_dir = Path(alembic_config.get_main_option("script_location"))
    create_vectorizer_migration(migrations_dir, config)
    
    # Run upgrade
    upgrade(alembic_config, "head")
    
    # Verify configuration
    with initialized_engine.connect() as conn:
        vectorizer = conn.execute(text("SELECT * FROM ai.vectorizer")).fetchone()
        assert vectorizer is not None
        config = str(dict(vectorizer._mapping))
        assert "vector_l1_ops" in config
        assert "16" in config  # m parameter
        assert "64" in config  # ef_construction
    
    # Run downgrade
    downgrade(alembic_config, "base")