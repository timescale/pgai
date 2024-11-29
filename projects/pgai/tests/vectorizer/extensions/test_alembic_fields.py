from pathlib import Path

from alembic.command import upgrade
from alembic.config import Config
from sqlalchemy import Engine, text

from pgai.configuration import (
    ChunkingConfig,
    CreateVectorizerParams,
    DiskANNIndexingConfig,
    HNSWIndexingConfig,
    NoIndexingConfig,
    NoSchedulingConfig,
    OllamaEmbeddingConfig,
    OpenAIEmbeddingConfig,
    ProcessingConfig,
    SchedulingConfig,
)
from pgai.vectorizer import Vectorizer
from tests.vectorizer.extensions.conftest import load_template

default_embedding_config = OpenAIEmbeddingConfig(
    model="text-embedding-3-small",
    dimensions=768,
    chat_user="test_user",
    api_key_name="test_key",
)

default_chunking_config = ChunkingConfig(
    chunk_column="content",
    chunk_size=500,
    chunk_overlap=10,
    separator=" ",
    is_separator_regex=True,
)

default_scheduling_config = SchedulingConfig(
    schedule_interval="1h",
    initial_start="2022-01-01T00:00:00Z",
    fixed_schedule=True,
    timezone="UTC",
)

default_processing_config = ProcessingConfig(batch_size=10, concurrency=5)

default_indexing_config = DiskANNIndexingConfig(
    min_rows=10,
    storage_layout="plain",
    num_neighbors=5,
    search_list_size=10,
    max_alpha=0.5,
    num_dimensions=10,
    num_bits_per_dimension=10,
    create_when_queue_empty=False,
)


def setup_migrations(
    alembic_config: Config,
    engine: Engine,
    embedding_config: OpenAIEmbeddingConfig | OllamaEmbeddingConfig | None = None,
    chunking_config: ChunkingConfig | None = None,
    scheduling_config: SchedulingConfig | NoSchedulingConfig | None = None,
    processing_config: ProcessingConfig | None = None,
    indexing_config: DiskANNIndexingConfig
    | HNSWIndexingConfig
    | NoIndexingConfig
    | None = None,
) -> tuple[
    OpenAIEmbeddingConfig | OllamaEmbeddingConfig,
    ChunkingConfig,
    SchedulingConfig | NoSchedulingConfig,
    ProcessingConfig,
    DiskANNIndexingConfig | HNSWIndexingConfig | NoIndexingConfig,
]:
    migrations_dir = Path(alembic_config.get_main_option("script_location"))  # type: ignore
    versions_dir = migrations_dir / "versions"

    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE SCHEMA IF NOT EXISTS timescale;
                CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
                """
            )
        )
        conn.commit()

    if embedding_config is None:
        embedding_config = default_embedding_config

    if chunking_config is None:
        chunking_config = default_chunking_config

    if scheduling_config is None:
        scheduling_config = default_scheduling_config

    if processing_config is None:
        processing_config = default_processing_config

    if indexing_config is None:
        indexing_config = default_indexing_config

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
        embedding=embedding_config.to_python_arg(),
        chunking=chunking_config.to_python_arg(),
        scheduling=scheduling_config.to_python_arg(),
        processing=processing_config.to_python_arg(),
        indexing=indexing_config.to_python_arg(),
    )
    with open(versions_dir / "002_create_vectorizer.py", "w") as f:
        f.write(vectorizer_content)

    return (
        embedding_config,
        chunking_config,
        scheduling_config,
        processing_config,
        indexing_config,
    )


def compare_db_vectorizer_with_configs(
    engine: Engine,
    embedding_config: OpenAIEmbeddingConfig | OllamaEmbeddingConfig | None = None,
    chunking_config: ChunkingConfig | None = None,
    scheduling_config: SchedulingConfig | NoSchedulingConfig | None = None,
    processing_config: ProcessingConfig | None = None,
    indexing_config: DiskANNIndexingConfig
    | HNSWIndexingConfig
    | NoIndexingConfig
    | None = None,
):
    if embedding_config is None:
        embedding_config = default_embedding_config

    if chunking_config is None:
        chunking_config = default_chunking_config

    if scheduling_config is None:
        scheduling_config = default_scheduling_config

    if processing_config is None:
        processing_config = default_processing_config

    if indexing_config is None:
        indexing_config = default_indexing_config
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                    select pg_catalog.to_jsonb(v) as vectorizer from ai.vectorizer v
                """)
        ).fetchall()
        assert len(rows) == 1
        parsed_vectorizer = Vectorizer.model_validate(rows[0].vectorizer)  # type: ignore
        params = CreateVectorizerParams.from_db_config(parsed_vectorizer)

        assert params.embedding == embedding_config
        assert params.chunking == chunking_config
        assert params.processing == processing_config
        assert params.indexing == indexing_config
        if isinstance(scheduling_config, NoSchedulingConfig):
            assert params.scheduling == scheduling_config
        # Note that a scheduling config can currently not be compared because
        # the representation of time in the db is different
        # from the representation in the config object


def test_vectorizer_migration_default_fields(
    alembic_config: Config, initialized_engine: Engine
):
    """Test vectorizer creation with a bunch of fields"""
    setup_migrations(alembic_config, initialized_engine)
    upgrade(alembic_config, "head")

    compare_db_vectorizer_with_configs(initialized_engine)


def test_vectorizer_migration_ollama(
    alembic_config: Config, initialized_engine: Engine
):
    """Test vectorizer creation with a bunch of fields"""
    embedding_config = OllamaEmbeddingConfig(
        model="nomic-embed-text",
        dimensions=100,
        base_url="http://localhost:8000",
        truncate=False,
        keep_alive="1h",
    )

    setup_migrations(
        alembic_config, initialized_engine, embedding_config=embedding_config
    )
    upgrade(alembic_config, "head")

    compare_db_vectorizer_with_configs(
        initialized_engine, embedding_config=embedding_config
    )


def test_vectorizer_migration_chunking_recursive(
    alembic_config: Config, initialized_engine: Engine
):
    """Test vectorizer creation with recursive character text splitter configuration"""
    chunking_config = ChunkingConfig(
        chunk_column="content",
        chunk_size=1000,
        chunk_overlap=100,
        separator=["\n\n", "\n", ".", "!", "?"],
        is_separator_regex=True,
    )

    setup_migrations(
        alembic_config, initialized_engine, chunking_config=chunking_config
    )
    upgrade(alembic_config, "head")

    compare_db_vectorizer_with_configs(
        initialized_engine,
        chunking_config=chunking_config,
    )


def test_vectorizer_migration_chunking_simple(
    alembic_config: Config, initialized_engine: Engine
):
    """Test vectorizer creation with simple character text splitter configuration"""
    chunking_config = ChunkingConfig(
        chunk_column="content",
        chunk_size=200,  # Small chunk size
        chunk_overlap=50,
        separator=" ",  # Single simple separator
        is_separator_regex=False,
    )

    setup_migrations(
        alembic_config, initialized_engine, chunking_config=chunking_config
    )
    upgrade(alembic_config, "head")
    compare_db_vectorizer_with_configs(
        initialized_engine, chunking_config=chunking_config
    )


def test_vectorizer_migration_chunking_regex(
    alembic_config: Config, initialized_engine: Engine
):
    """Test vectorizer creation with regex separator configuration"""
    chunking_config = ChunkingConfig(
        chunk_column="content",
        chunk_size=800,
        chunk_overlap=200,
        separator=r"\s+",  # Regex for whitespace
        is_separator_regex=True,
    )

    setup_migrations(
        alembic_config, initialized_engine, chunking_config=chunking_config
    )
    upgrade(alembic_config, "head")
    compare_db_vectorizer_with_configs(
        initialized_engine, chunking_config=chunking_config
    )


def test_vectorizer_migration_hnsw_cosine(
    alembic_config: Config, initialized_engine: Engine
):
    """Test vectorizer creation with HNSW cosine indexing"""
    indexing_config = HNSWIndexingConfig(
        min_rows=50000,
        opclass="vector_cosine_ops",
        m=16,
        ef_construction=64,
        create_when_queue_empty=True,
    )

    setup_migrations(
        alembic_config, initialized_engine, indexing_config=indexing_config
    )
    upgrade(alembic_config, "head")
    compare_db_vectorizer_with_configs(
        initialized_engine, indexing_config=indexing_config
    )


def test_vectorizer_migration_hnsw_l1(
    alembic_config: Config, initialized_engine: Engine
):
    """Test vectorizer creation with HNSW L1 indexing"""
    indexing_config = HNSWIndexingConfig(
        min_rows=75000,
        opclass="vector_l1_ops",
        m=32,
        ef_construction=128,
        create_when_queue_empty=False,
    )

    setup_migrations(
        alembic_config, initialized_engine, indexing_config=indexing_config
    )
    upgrade(alembic_config, "head")
    compare_db_vectorizer_with_configs(
        initialized_engine, indexing_config=indexing_config
    )


def test_vectorizer_migration_diskann_minimal(
    alembic_config: Config, initialized_engine: Engine
):
    indexing_config = DiskANNIndexingConfig()

    setup_migrations(
        alembic_config, initialized_engine, indexing_config=indexing_config
    )
    upgrade(alembic_config, "head")
    compare_db_vectorizer_with_configs(
        initialized_engine, indexing_config=indexing_config
    )


def test_vectorizer_migration_no_scheduling(
    alembic_config: Config, initialized_engine: Engine
):
    """Test vectorizer creation with no scheduling"""
    scheduling_config = NoSchedulingConfig()
    indexing_config = NoIndexingConfig()

    setup_migrations(
        alembic_config,
        initialized_engine,
        scheduling_config=scheduling_config,
        indexing_config=indexing_config,
    )
    upgrade(alembic_config, "head")
    compare_db_vectorizer_with_configs(
        initialized_engine,
        scheduling_config=scheduling_config,
        indexing_config=indexing_config,
    )


def test_vectorizer_migration_custom_schedule(
    alembic_config: Config, initialized_engine: Engine
):
    """Test vectorizer creation with custom scheduling"""
    scheduling_config = SchedulingConfig(
        schedule_interval="30m",
        initial_start="2024-03-20T00:00:00Z",
        fixed_schedule=True,
        timezone="America/New_York",
    )

    setup_migrations(
        alembic_config, initialized_engine, scheduling_config=scheduling_config
    )
    upgrade(alembic_config, "head")
    compare_db_vectorizer_with_configs(
        initialized_engine, scheduling_config=scheduling_config
    )


def test_vectorizer_migration_flexible_schedule(
    alembic_config: Config, initialized_engine: Engine
):
    """Test vectorizer creation with flexible scheduling"""
    scheduling_config = SchedulingConfig(
        schedule_interval="2h", fixed_schedule=False, timezone="UTC"
    )

    setup_migrations(
        alembic_config, initialized_engine, scheduling_config=scheduling_config
    )
    upgrade(alembic_config, "head")
    compare_db_vectorizer_with_configs(
        initialized_engine, scheduling_config=scheduling_config
    )
