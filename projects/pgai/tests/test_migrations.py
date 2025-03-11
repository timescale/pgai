from typing import Any

from pydantic.dataclasses import dataclass

from pgai.vectorizer.migrations import register_migration
from pgai.vectorizer.vectorizer import Config

config_0_9_0 = {
    "version": "0.9.0",
    "chunking": {
        "separator": "\n\n",
        "chunk_size": 128,
        "config_type": "chunking",
        "chunk_column": "body",
        "chunk_overlap": 10,
        "implementation": "character_text_splitter",
        "is_separator_regex": False,
    },
    "indexing": {"config_type": "indexing", "implementation": "none"},
    "embedding": {
        "model": "text-embedding-3-small",
        "dimensions": 768,
        "config_type": "embedding",
        "api_key_name": "OPENAI_API_KEY",
        "implementation": "openai",
    },
    "formatting": {
        "template": "title: $title published: $published $chunk",
        "config_type": "formatting",
        "implementation": "python_template",
    },
    "processing": {"config_type": "processing", "implementation": "default"},
    "scheduling": {
        "job_id": 1000,
        "timezone": "America/Chicago",
        "config_type": "scheduling",
        "initial_start": "2050-01-06T00:00:00+00:00",
        "implementation": "timescaledb",
        "schedule_interval": "00:05:00",
    },
}


config_0_10_0 = {
    "version": "0.10.0",
    "loading": {
        "config_type": "loading",
        "implementation": "column",
        "retries": 6,
        "column_name": "body",
    },
    "parsing": {"config_type": "parsing", "implementation": "none"},
    "chunking": {
        "separator": "\n\n",
        "chunk_size": 128,
        "config_type": "chunking",
        "chunk_overlap": 10,
        "implementation": "character_text_splitter",
        "is_separator_regex": False,
    },
    "indexing": {"config_type": "indexing", "implementation": "none"},
    "embedding": {
        "model": "text-embedding-3-small",
        "dimensions": 768,
        "config_type": "embedding",
        "api_key_name": "OPENAI_API_KEY",
        "implementation": "openai",
    },
    "formatting": {
        "template": "title: $title published: $published $chunk",
        "config_type": "formatting",
        "implementation": "python_template",
    },
    "processing": {"config_type": "processing", "implementation": "default"},
    "scheduling": {
        "job_id": 1000,
        "timezone": "America/Chicago",
        "config_type": "scheduling",
        "initial_start": "2050-01-06T00:00:00+00:00",
        "implementation": "timescaledb",
        "schedule_interval": "00:05:00",
    },
}


def test_multiple_migrations():
    @dataclass
    class SimpleConfig:
        version: str

    # register some migrations
    def migration_func_1_2(old_conf: SimpleConfig) -> dict[str, Any]:
        assert old_conf.version == "0.0.1"
        return {"version": "0.0.2"}

    def migration_func_2_0_9(old_conf: SimpleConfig) -> dict[str, Any]:
        assert old_conf.version == "0.0.2"
        return config_0_9_0

    register_migration("0.0.2", SimpleConfig, "1 to 2")(migration_func_1_2)
    register_migration("0.9.0", SimpleConfig, "2 to 0.9.0")(migration_func_2_0_9)

    migrated_config = Config(version="0.0.1")  # pyright: ignore [reportCallIssue]
    expected_config = Config(**config_0_10_0)  # pyright: ignore [reportArgumentType]

    assert migrated_config == expected_config


def test_migrate_config_from_ext_version_0_9_to_0_10():
    migrated_config = Config(**config_0_9_0)  # pyright: ignore [reportArgumentType]
    expected_config = Config(**config_0_10_0)  # pyright: ignore [reportArgumentType]

    assert migrated_config == expected_config
