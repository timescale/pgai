import importlib
from pathlib import Path

from alembic.command import revision, upgrade
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

from tests.vectorizer.extensions.conftest import load_template


def create_model_file(models_dir: Path) -> None:
    """Create the BlogPost model file"""
    models_dir.mkdir(exist_ok=True)

    # Create __init__.py
    with open(models_dir / "__init__.py", "w"):
        pass

    # Create models.py with BlogPost model
    model_content = load_template(
        "models/blog_post.py.template",
        model="text-embedding-3-small",
        dimensions=768,
        chunk_size=500,
        chunk_overlap=50,
        template="Title: $title\\nContent: $chunk",
    )
    with open(models_dir / "models.py", "w") as f:
        f.write(model_content)


def create_all_fields_model_file(models_dir: Path) -> None:
    """Create the BlogPost model file"""
    models_dir.mkdir(exist_ok=True)

    # Create __init__.py
    with open(models_dir / "__init__.py", "w"):
        pass

    # Create models.py with BlogPost model
    model_content = load_template("models/blog_post_all_fields.py.template")
    with open(models_dir / "models.py", "w") as f:
        f.write(model_content)


def create_autogen_env(migrations_dir: Path) -> None:
    """Create the Alembic environment for autogeneration"""
    env_content = load_template("alembic/autogen_env.py.template")
    with open(migrations_dir / "env.py", "w") as f:
        f.write(env_content)


def test_vectorizer_autogeneration(
    alembic_config: Config,
    initialized_engine: Engine,
    cleanup_modules: None,  # noqa: ARG001
):
    """Test automatic generation of vectorizer migrations"""
    migrations_dir = Path(alembic_config.get_main_option("script_location"))  # type: ignore
    models_dir = migrations_dir.parent / "models"

    # Setup model and env files
    create_model_file(models_dir)
    create_autogen_env(migrations_dir)

    # Generate initial migration
    revision(
        alembic_config,
        message="create blog posts table and vectorizer",
        autogenerate=True,
    )

    # Read the generated migration file to verify its contents
    versions_dir = migrations_dir / "versions"
    migration_file = next(versions_dir.glob("*.py"))
    with open(migration_file) as f:
        migration_contents = f.read()

    # Verify migration contains expected operations
    assert "op.create_table('blog_posts'" in migration_contents
    assert "op.create_vectorizer" in migration_contents
    assert "'text-embedding-3-small'" in migration_contents
    assert "dimensions=768" in migration_contents
    assert "chunk_size=500" in migration_contents
    assert "chunk_overlap=50" in migration_contents
    assert "'Title: $title\\nContent: $chunk'" in migration_contents

    # Run the migration
    upgrade(alembic_config, "head")

    # Verify table creation
    inspector = inspect(initialized_engine)
    tables = inspector.get_table_names()
    assert "blog_posts" in tables

    # Verify vectorizer creation
    with initialized_engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM ai.vectorizer_status")).fetchone()
        assert result is not None
        assert result.source_table == "public.blog_posts"

    # Now modify the model to test detecting changes
    model_content = load_template(
        "models/blog_post.py.template",
        model="text-embedding-3-large",
        dimensions=1536,
        chunk_size=500,
        chunk_overlap=50,
        template="Title: $title\\nContent: $chunk",
    )
    with open(models_dir / "models.py", "w") as f:
        f.write(model_content)

    # Reload models module to pick up changes

    import models.models  # type: ignore

    importlib.reload(models.models)  # type: ignore

    # Generate migration for the changes
    revision(
        alembic_config, message="update vectorizer configuration", autogenerate=True
    )

    # Verify the new migration contains vectorizer updates
    new_migration_file = max(versions_dir.glob("*update_vectorizer_configuration.py"))
    with open(new_migration_file) as f:
        migration_contents = f.read()

    assert "op.drop_vectorizer(1, drop_all=True)" in migration_contents
    assert "op.create_vectorizer" in migration_contents
    assert "'text-embedding-3-large'" in migration_contents
    assert "dimensions=1536" in migration_contents


def test_vectorizer_all_fields_autogeneration(
    alembic_config: Config,
    initialized_engine: Engine,
    cleanup_modules: None,  # noqa: ARG001
):
    """Test automatic generation of vectorizer migrations for all fields"""
    migrations_dir = Path(alembic_config.get_main_option("script_location"))  # type: ignore
    models_dir = migrations_dir.parent / "models"

    # Setup model and env files
    create_all_fields_model_file(models_dir)
    create_autogen_env(migrations_dir)

    # Generate initial migration
    revision(
        alembic_config,
        message="create blog posts table and vectorizer",
        autogenerate=True,
    )

    # Read the generated migration file to verify its contents
    versions_dir = migrations_dir / "versions"
    migration_file = next(versions_dir.glob("*.py"))
    with open(migration_file) as f:
        migration_contents = f.read()

    # Verify base table creation
    assert "op.create_table('blog_posts'" in migration_contents

    assert ("from pgai.configuration import ChunkingConfig, DiskANNIndexingConfig,"
            " EmbeddingConfig, ProcessingConfig, SchedulingConfig") in migration_contents

    # Verify vectorizer creation and basic config
    assert "op.create_vectorizer" in migration_contents
    assert "'blog_posts'" in migration_contents

    # Verify embedding config
    assert "embedding=EmbeddingConfig" in migration_contents
    assert "model='text-embedding-3-small'" in migration_contents
    assert "dimensions=768" in migration_contents
    assert "chat_user='test_user'" in migration_contents
    assert "api_key_name='test_key'" in migration_contents

    # Verify chunking config
    assert "chunking=ChunkingConfig" in migration_contents
    assert "chunk_column='content'" in migration_contents
    assert "chunk_size=500" in migration_contents
    assert "chunk_overlap=10" in migration_contents
    assert "separator=' '" in migration_contents
    assert "is_separator_regex=True" in migration_contents

    # Verify formatting template
    assert "formatting_template='Title: $title\\nContent: $chunk'" in migration_contents

    # Verify DiskANN indexing config
    assert "indexing=DiskANNIndexingConfig" in migration_contents
    assert "min_rows=10" in migration_contents
    assert "storage_layout='plain'" in migration_contents
    assert "num_neighbors=5" in migration_contents
    assert "search_list_size=10" in migration_contents
    assert "max_alpha=0.5" in migration_contents
    assert "num_dimensions=10" in migration_contents
    assert "num_bits_per_dimension=10" in migration_contents
    assert "create_when_queue_empty=False" in migration_contents

    # Verify scheduling config
    assert "scheduling=SchedulingConfig" in migration_contents
    assert "schedule_interval='1h'" in migration_contents
    assert "initial_start='2022-01-01T00:00:00Z'" in migration_contents
    assert "fixed_schedule=True" in migration_contents
    assert "timezone='UTC'" in migration_contents

    # Verify processing config
    assert "processing=ProcessingConfig" in migration_contents
    assert "batch_size=10" in migration_contents
    assert "concurrency=5" in migration_contents

    # Verify schema and table configurations
    assert "target_schema='timescale'" in migration_contents
    assert "target_table='blog_posts_embedding'" in migration_contents
    assert "view_schema='timescale'" in migration_contents
    assert "view_name='blog_posts_embedding_view'" in migration_contents
    assert "queue_schema='timescale'" in migration_contents
    assert "queue_table='blog_posts_embedding_queue'" in migration_contents

    # Verify grants and enqueue settings
    assert "grant_to=['test_user', 'test_user2']" in migration_contents


def test_multiple_vectorizer_fields_autogeneration(
        alembic_config: Config,
        initialized_engine: Engine,
        cleanup_modules: None,  # noqa: ARG001
):
    """Test automatic generation of migrations with multiple vectorizer fields"""
    migrations_dir = Path(alembic_config.get_main_option("script_location"))  # type: ignore
    models_dir = migrations_dir.parent / "models"
    models_dir.mkdir(exist_ok=True)

    # Create __init__.py
    with open(models_dir / "__init__.py", "w"):
        pass

    # Create initial model with two vectorizer fields
    model_content = """
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, Text
from pgai.sqlalchemy import VectorizerField, EmbeddingConfig, ChunkingConfig

Base = declarative_base()

class BlogPost(Base):
    __tablename__ = "blog_posts"

    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)

    content_embeddings = VectorizerField(
        embedding=EmbeddingConfig(
            model="text-embedding-3-small",
            dimensions=768
        ),
        chunking=ChunkingConfig(
            chunk_column="content",
            chunk_size=500,
            chunk_overlap=50
        ),
        formatting_template="Title: $title\\nContent: $chunk"
    )

    summary_embeddings = VectorizerField(
        embedding=EmbeddingConfig(
            model="text-embedding-3-small",
            dimensions=768
        ),
        chunking=ChunkingConfig(
            chunk_column="summary",
            chunk_size=200,
            chunk_overlap=20
        ),
        formatting_template="$chunk",
    )
"""
    with open(models_dir / "models.py", "w") as f:
        f.write(model_content)

    create_autogen_env(migrations_dir)

    # Generate initial migration
    revision(
        alembic_config,
        message="create blog posts table with two vectorizers",
        autogenerate=True,
    )

    # Run the migration
    upgrade(alembic_config, "head")

    # Verify both vectorizers were created
    with initialized_engine.connect() as conn:
        results = conn.execute(text("SELECT * FROM ai.vectorizer_status ORDER BY id")).fetchall()
        assert len(results) == 2
        assert results[0].source_table == "public.blog_posts"  # content vectorizer
        assert results[1].source_table == "public.blog_posts"  # summary vectorizer

    # Modify only the content vectorizer configuration
    modified_model_content = """
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, Text
from pgai.sqlalchemy import VectorizerField, EmbeddingConfig, ChunkingConfig

Base = declarative_base()

class BlogPost(Base):
    __tablename__ = "blog_posts"

    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)

    content_embeddings = VectorizerField(
        embedding=EmbeddingConfig(
            model="text-embedding-3-large",
            dimensions=1536
        ),
        chunking=ChunkingConfig(
            chunk_column="content",
            chunk_size=500,
            chunk_overlap=50
        ),
        formatting_template="Title: $title\\nContent: $chunk"
    )

    summary_embeddings = VectorizerField(
        embedding=EmbeddingConfig(
            model="text-embedding-3-small",
            dimensions=768
        ),
        chunking=ChunkingConfig(
            chunk_column="summary",
            chunk_size=200,
            chunk_overlap=20
        ),
        formatting_template="$chunk"
    )
"""
    with open(models_dir / "models.py", "w") as f:
        f.write(modified_model_content)

    # Reload models module to pick up changes
    import models.models  # type: ignore
    importlib.reload(models.models)  # type: ignore

    # Generate migration for the changes
    revision(
        alembic_config,
        message="update content vectorizer configuration",
        autogenerate=True,
    )

    # Verify the new migration updates only the content vectorizer
    versions_dir = migrations_dir / "versions"
    new_migration_file = max(versions_dir.glob("*update_content_vectorizer_configuration.py"))
    with open(new_migration_file) as f:
        migration_contents = f.read()

    # Should only drop and recreate the content vectorizer (id=1)
    assert "op.drop_vectorizer(1, drop_all=True)" in migration_contents
    assert "op.create_vectorizer" in migration_contents
    assert "'text-embedding-3-large'" in migration_contents
    assert "dimensions=1536" in migration_contents

    # Should not contain changes to summary vectorizer
    assert "text-embedding-3-small" not in migration_contents
    assert "dimensions=768" not in migration_contents
    assert "chunk_size=200" not in migration_contents

    # Run the migration
    upgrade(alembic_config, "head")

    # Verify final state - both vectorizers should still exist, with updated config
    with initialized_engine.connect() as conn:
        results = conn.execute(text("""
            SELECT source_table, config->>'embedding' as embedding
            FROM ai.vectorizer 
            ORDER BY id
        """)).fetchall()
        assert len(results) == 2

        # Verify content vectorizer was updated
        assert '"model": "text-embedding-3-large"' in results[0].embedding
        assert '"dimensions": 1536' in results[0].embedding

        # Verify summary vectorizer was unchanged
        assert '"model": "text-embedding-3-small"' in results[1].embedding
        assert '"dimensions": 768' in results[1].embedding