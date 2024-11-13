import tempfile
from pathlib import Path

import alembic.config
from sqlalchemy import create_engine, inspect, text


def create_alembic_ini(alembic_dir: Path) -> Path:
    """Create a basic alembic.ini file"""
    ini_path = alembic_dir / "alembic.ini"
    with open(ini_path, "w") as f:
        f.write("""[alembic]
script_location = migrations
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stdout,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
""")
    return ini_path

def create_alembic_env(alembic_dir: Path, db_url: str) -> None:
    """Create a basic env.py file"""
    env_dir = alembic_dir / "migrations"
    env_dir.mkdir(exist_ok=True)

    with open(env_dir / "env.py", "w") as f:
        f.write("""from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def run_migrations_online():
    connectable = context.config.attributes.get('connection', None)
    if connectable is None:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None
        )

        with context.begin_transaction():
            context.run_migrations()

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=None, literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
""")

def create_migration_script(migrations_dir: Path) -> None:
    """Create a basic migration script"""
    versions_dir = migrations_dir / "versions"
    versions_dir.mkdir(exist_ok=True)

    with open(versions_dir / "001_create_test_table.py", "w") as f:
        f.write("""\"\"\"create test table

Revision ID: 001
Revises: 
Create Date: 2024-03-19 10:00:00.000000

\"\"\"
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'test_table',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(50), nullable=False)
    )

def downgrade():
    op.drop_table('test_table')
""")


def create_vectorizer_migration_script(migrations_dir: Path) -> None:
    """Create migration scripts for vectorizer testing"""
    versions_dir = migrations_dir / "versions"
    versions_dir.mkdir(exist_ok=True)

    # First migration - create blog table
    with open(versions_dir / "001_create_blog_table.py", "w") as f:
        f.write('''"""create blog table

Revision ID: 001
Revises: 
Create Date: 2024-03-19 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'blog',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('content', sa.Text, nullable=False)
    )

def downgrade():
    op.drop_table('blog')
''')

    # Second migration - create vectorizer
    with open(versions_dir / "002_create_vectorizer.py", "w") as f:
        f.write('''"""create vectorizer

Revision ID: 002
Revises: 001
Create Date: 2024-03-19 10:01:00.000000
"""
from alembic import op
from pgai.extensions.alembic.operations import (
    CreateVectorizerOp, 
    EmbeddingConfig,
    ChunkingConfig,
    FormattingConfig
)
from sqlalchemy import text

# revision identifiers
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade():
    op.create_vectorizer(
        'blog',
        destination='blog_embeddings',
        embedding=EmbeddingConfig(
            model='text-embedding-3-small',
            dimensions=768
        ),
        chunking=ChunkingConfig(
            chunk_column='content',
            chunk_size=700
        ),
        formatting=FormattingConfig(
            template='$title - $chunk'
        )
    )

def downgrade():
    connection = op.get_bind()
    result = connection.execute(
        text("SELECT id FROM ai.vectorizer WHERE source_table = 'blog'")
    ).scalar()
    if result:
        print(f"Found vectorizer with ID: {result}")  # Debug print
        op.drop_vectorizer(result)
    else:
        print("No vectorizer found!")  # Debug print
''')


def test_basic_alembic_migration(postgres_container):
    """Verify basic Alembic functionality works before testing vectorizer operations"""
    db_url = postgres_container.get_connection_url()
    engine = create_engine(db_url)

    # Create temp migration directory and set up Alembic environment
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create Alembic files
        alembic_ini = create_alembic_ini(temp_path)
        create_alembic_env(temp_path, db_url)
        create_migration_script(temp_path / "migrations")

        # Configure Alembic
        config = alembic.config.Config(alembic_ini)
        config.set_main_option("script_location", str(temp_path / "migrations"))
        config.set_main_option("sqlalchemy.url", db_url)
        config.attributes["connection"] = engine

        # Run upgrade
        alembic.command.upgrade(config, "head")

        # Verify table exists
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "test_table" in tables

        # Check table structure
        columns = {col["name"]: col["type"].__class__.__name__
                   for col in inspector.get_columns("test_table")}
        assert columns["id"] == "INTEGER"
        assert columns["name"] == "VARCHAR"

        # Run downgrade
        alembic.command.downgrade(config, "base")

        # Verify table is gone
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "test_table" not in tables


def test_vectorizer_migration(postgres_container):
    """Test vectorizer creation and deletion via Alembic migrations"""
    
    db_url = postgres_container.get_connection_url()
    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("""
                CREATE EXTENSION IF NOT EXISTS ai CASCADE;
            """))
        conn.commit()

    # Create temp migration directory and set up Alembic environment
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create Alembic files
        alembic_ini = create_alembic_ini(temp_path)
        create_alembic_env(temp_path, db_url)
        create_vectorizer_migration_script(temp_path / "migrations")

        # Configure Alembic
        config = alembic.config.Config(alembic_ini)
        config.set_main_option("script_location", str(temp_path / "migrations"))
        config.set_main_option("sqlalchemy.url", db_url)
        config.attributes["connection"] = engine

        # Run upgrade to first migration (create blog table)
        alembic.command.upgrade(config, "001")

        # Verify blog table exists
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "blog" in tables

        # Run upgrade to second migration (create vectorizer)
        alembic.command.upgrade(config, "002")

        # Verify vectorizer exists
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM ai.vectorizer_status")).fetchone()
            assert result is not None
            assert result.source_table == "public.blog"
            assert result.pending_items == 0  # Since table is empty

        # Run downgrade of vectorizer
        alembic.command.downgrade(config, "001")

        # Verify vectorizer is gone but blog table remains
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM ai.vectorizer_status")).fetchall()
            assert len(result) == 0

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "blog" in tables

        # Run final downgrade
        alembic.command.downgrade(config, "base")

        # Verify everything is gone
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "blog" not in tables
