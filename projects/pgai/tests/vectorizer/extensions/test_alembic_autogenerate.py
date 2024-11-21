import importlib
from pathlib import Path

from alembic.command import revision, upgrade
from alembic.config import Config
from sqlalchemy import Engine, inspect, text

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

    assert "op.drop_vectorizer(1, drop_objects=True)" in migration_contents
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

    # Verify migration contains expected operations
    assert "op.create_table('blog_posts'" in migration_contents
    assert "op.create_vectorizer" in migration_contents
    assert "'text-embedding-3-small'" in migration_contents
    assert "dimensions=768" in migration_contents
    assert "chunk_size=500" in migration_contents
    assert "chunk_overlap=10" in migration_contents
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