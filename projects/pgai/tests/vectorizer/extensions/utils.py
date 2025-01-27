from pathlib import Path
from typing import Any

from sqlalchemy import Column

from tests.vectorizer.extensions.conftest import load_template


def create_vectorizer_migration(
    migrations_dir: Path,
    table_name: str,
    table_columns: list[Column],  # type: ignore
    vectorizer_config: dict[str, Any],
    revision_id: str = "001",
    revises: str = "",
    create_date: str = "2024-03-19 10:00:00.000000",
    down_revision: str = "None",
) -> None:
    """Create a vectorizer migration with the given configuration.

    Args:
        migrations_dir: Directory where migration files are stored
        table_name: Name of the source table to create
        table_columns: List of SQLAlchemy Column objects defining table structure
        vectorizer_config: Dictionary of vectorizer configuration options
        revision_id: Migration revision ID (default: "001")
        revises: What this migration revises (default: "")
        create_date: Migration creation date (default: current timestamp)
        down_revision: Previous revision (default: None)
    """
    versions_dir = migrations_dir / "versions"

    migration_content = load_template(
        "migrations/universal_vectorizer.py.template",
        revision_id=revision_id,
        revises=revises,
        create_date=create_date,
        down_revision=down_revision,
        table_name=table_name,
        table_columns=table_columns,  # type: ignore
        vectorizer_config=vectorizer_config,  # type: ignore
    )

    with open(
        versions_dir / f"{revision_id}_create_{table_name}_vectorizer.py", "w"
    ) as f:
        f.write(migration_content)
