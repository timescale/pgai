import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from alembic.script import ScriptDirectory
from dotenv import load_dotenv
from pgai.alembic import register_operations
from sqlalchemy.engine import Connection

# Import your models and config
from pgai_discord_bot.main import Base
from pgai_discord_bot.main import engine as async_engine

load_dotenv()
register_operations()

# this is the Alembic Config object
config = context.config

config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"].replace("\n", ""))

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the target metadata
target_metadata = Base.metadata


def process_revision_directives(context, revision, directives):
    # extract Migration
    migration_script = directives[0]
    # extract current head revision
    head_revision = ScriptDirectory.from_config(context.config).get_current_head()

    if head_revision is None:
        # edge case with first migration
        new_rev_id = 1
    else:
        # default branch with incrementation
        last_rev_id = int(head_revision.lstrip("0"))
        new_rev_id = last_rev_id + 1
    # fill zeros up to 4 digits: 1 -> 0001
    migration_script.rev_id = f"{new_rev_id:04}"


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in target_metadata.info.get(
        "pgai_managed_tables", set()
    ):
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=process_revision_directives,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        process_revision_directives=process_revision_directives,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context."""

    connectable = async_engine

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
