import importlib
import pkgutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

import semver
import structlog

logger = structlog.get_logger()

# config generic type
C = TypeVar("C")
MigrationFunc = Callable[[C], dict[str, Any]]


@dataclass
class Migration(Generic[C]):
    version: str  # target version
    source_config_class: type[C]  # config dataclass for the source version
    apply: MigrationFunc[C]
    description: str = ""


# registry to hold all migrations
migrations: list[Migration[Any]] = []

MigrationDecorator = Callable[[MigrationFunc[C]], MigrationFunc[C]]


def register_migration(
    version: str, source_config_class: type[C], description: str = ""
) -> MigrationDecorator[C]:
    """
    Decorator to register a migration function with
    config class validation
    """

    def decorator(func: MigrationFunc[C]) -> MigrationFunc[C]:
        migrations.append(
            Migration(
                version=version,
                source_config_class=source_config_class,
                apply=func,
                description=description,
            )
        )
        migrations.sort(key=lambda m: semver.VersionInfo.parse(m.version))
        return func

    return decorator


def get_latest_version() -> str:
    """Get the latest migration version available"""
    if not migrations:
        return "0.0.0"
    return migrations[-1].version


def apply_migrations(data: dict[str, Any]) -> dict[str, Any]:
    """
    Apply all necessary migrations incrementally until reaching the latest version

    Args:
        data: The config data to migrate

    Returns:
        The migrated config data
    """
    if not data:
        return data

    # determine starting version
    current_version = data.get("version")
    if current_version is None:
        logger.warning(
            "Vectorizer Config migration can't be considered. "
            "Raw data does not contain a version field."
        )
        return data

    current = semver.VersionInfo.parse(current_version)
    latest = semver.VersionInfo.parse(get_latest_version())

    # no migrations needed if already at latest
    if current >= latest:
        return data

    result = dict(data)

    # only migrations with a version greater than the current version are applicable
    applicable_migrations = [
        m for m in migrations if current < semver.VersionInfo.parse(m.version)
    ]

    # migrations are applied sequentially
    for migration in applicable_migrations:
        logger.info(
            f"Applying Vectorizer Config migration "
            f"from version {current_version} "
            f"to version {migration.version}: {migration.description}"
        )

        # instantiate config class for this version so we can validate the input
        config_instance = migration.source_config_class(**result)

        result = migration.apply(config_instance)

        # updating the version after each successful migration so we
        # don't re-apply migrations
        current_version = migration.version
        result["version"] = migration.version

    return result


def load_migrations():
    """
    dynamically import all migration modules to register them
    through the register_migration decorator
    """
    package = sys.modules[__name__]
    modules = pkgutil.iter_modules(package.__path__, package.__name__ + ".")
    for _, name, is_pkg in modules:
        if not is_pkg:
            importlib.import_module(name)


load_migrations()
