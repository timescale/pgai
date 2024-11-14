import sys
import tempfile
from pathlib import Path

import alembic.config

from sqlalchemy import Column, Integer, Text, create_engine, text, inspect
from sqlalchemy.orm import declarative_base

from pgai.extensions.sqlalchemy import VectorizerField
from tests.vectorizer.extensions.test_alembic import create_alembic_ini, create_alembic_env


def create_script_mako(migrations_dir: Path) -> None:
    """Create the script.py.mako template file that Alembic uses to generate migration scripts."""

    versions_dir = migrations_dir / "versions"
    versions_dir.mkdir(exist_ok=True)
    
    with open(migrations_dir / "script.py.mako", "w") as f:
        f.write("""from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade():
    ${upgrades if upgrades else "pass"}


def downgrade():
    ${downgrades if downgrades else "pass"}
""")

def test_vectorizer_autogeneration(postgres_container):
    """Test automatic generation of vectorizer migrations"""
    
    db_url = postgres_container.get_connection_url()
    engine = create_engine(db_url)
    
    # Enable the AI extension
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE EXTENSION IF NOT EXISTS ai CASCADE;
        """))
        conn.commit()

    # Create our model
    Base = declarative_base()
    
    class BlogPost(Base):
        __tablename__ = "blog_posts_new"
        
        id = Column(Integer, primary_key=True)
        title = Column(Text, nullable=False)
        content = Column(Text, nullable=False)
        
        content_embeddings = VectorizerField(
            source_column="content",
            model="text-embedding-3-small",
            dimensions=768,
            chunk_size=500,
            chunk_overlap=50,
            formatting_template="Title: $title\nContent: $chunk"
        )

    # Set up temporary alembic environment
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        migrations_dir = temp_path / "migrations"
        
        # Create Alembic files
        alembic_ini = create_alembic_ini(temp_path)
        create_alembic_env(temp_path, db_url)
        create_script_mako(migrations_dir)

        # Save BlogPost model to a module file that env.py can import
        models_dir = temp_path / "models"
        models_dir.mkdir(exist_ok=True)
        with open(models_dir / "__init__.py", "w") as f:
            pass
            
        with open(models_dir / "models.py", "w") as f:
            f.write(f"""
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, Text
from pgai.extensions.sqlalchemy import VectorizerField

Base = declarative_base()

class BlogPost(Base):
    __tablename__ = "blog_posts"
    
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    
    content_embeddings = VectorizerField(
        source_column="content",
        model="text-embedding-3-small",
        dimensions=768,
        chunk_size=500,
        chunk_overlap=50,
        formatting_template="Title: $title\\nContent: $chunk"
    )
""")

        # Update env.py to import and use our models
        with open(migrations_dir / "env.py", "w") as f:
            f.write(f"""import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from pgai.extensions.sqlalchemy import compare_vectorizers
from pgai.extensions.alembic.operations import CreateVectorizerOp, DropVectorizerOp
from pgai.extensions.alembic.operations import render_create_vectorizer, render_drop_vectorizer

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import models
from models.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_online():
    connectable = context.config.attributes.get('connection', None)
    if connectable is None:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        
    def include_object(object, name, type_, reflected, compare_to):
        if object.info.get("pgai_managed", False):
            return False
        return True

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, include_object=include_object
        )

        with context.begin_transaction():
            context.run_migrations()

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=lambda obj, name, type_, reflected, compare_to: True
    )

    with context.begin_transaction():
        context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
""")

        # Configure Alembic
        config = alembic.config.Config(alembic_ini)
        config.set_main_option("script_location", str(migrations_dir))
        config.set_main_option("sqlalchemy.url", db_url)
        config.attributes["connection"] = engine
        
        # Add models directory to Python path
        sys.path.append(str(temp_path))

        # Generate initial migration
        alembic.command.revision(config,
            message="create blog posts table and vectorizer",
            autogenerate=True
        )

        # Read the generated migration file to verify its contents
        versions_dir = temp_path / "migrations" / "versions"
        migration_file = next(versions_dir.glob("*.py"))
        with open(migration_file) as f:
            migration_contents = f.read()

        # Verify the migration contains both table creation and vectorizer creation
        assert "op.create_table('blog_posts'" in migration_contents
        assert "op.create_vectorizer" in migration_contents
        assert "'text-embedding-3-small'" in migration_contents
        assert "dimensions=768" in migration_contents
        assert "chunk_size=500" in migration_contents
        assert "chunk_overlap=50" in migration_contents
        assert "'Title: $title\\nContent: $chunk'" in migration_contents

        # Run the migration
        alembic.command.upgrade(config, "head")

        # Verify both table and vectorizer were created
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "blog_posts" in tables

        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT * FROM ai.vectorizer_status"
            )).fetchone()
            assert result is not None
            assert result.source_table == "public.blog_posts"

        # Now modify the model to test detecting changes
        BlogPost.content_embeddings = VectorizerField(
            source_column="content",
            model="text-embedding-3-large",  # Changed model
            dimensions=1536,  # Changed dimensions
            chunk_size=1000,  # Changed chunk size
            chunk_overlap=100  # Changed overlap
        )

        # Generate migration for the changes
        alembic.command.revision(config,
                                 message="update vectorizer configuration",
                                 autogenerate=True
                                 )

        # Verify the new migration contains vectorizer updates
        new_migration_file = max(versions_dir.glob("*.py"))
        with open(new_migration_file) as f:
            migration_contents = f.read()

        assert "op.drop_vectorizer" in migration_contents
        assert "op.create_vectorizer" in migration_contents
        assert "'text-embedding-3-large'" in migration_contents
        assert "dimensions=1536" in migration_contents

        # Run migrations back to base
        alembic.command.downgrade(config, "base")

        # Verify everything is cleaned up
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "blog_posts" not in tables

        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT * FROM ai.vectorizer_status"
            )).fetchall()
            assert len(result) == 0