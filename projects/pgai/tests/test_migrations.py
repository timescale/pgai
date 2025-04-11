from typing import Any

import pytest
from pydantic import BaseModel

from pgai.vectorizer.migrations import migrations as global_migrations
from pgai.vectorizer.migrations import register_migration
from pgai.vectorizer.vectorizer import Vectorizer

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
    "destination": {
        "config_type": "destination",
        "implementation": "table",
        "target_schema": "public",
        "target_table": "target",
    },
}

vectorizer_fields = {
    "id": 1,
    "queue_schema": "public",
    "queue_table": "queue",
    "source_schema": "public",
    "source_table": "source",
    "target_schema": "public",
    "target_table": "target",
    "source_pk": [
        {
            "attname": "id",
            "pknum": 1,
            "attnum": 1,
        }
    ],
}


@pytest.fixture(autouse=True)
def clean_migrations():
    """
    Fixture to preserve and restore the global migrations list.
    This ensures that migrations registered in tests don't affect other tests.
    """
    # Save the original migrations list
    original_migrations = global_migrations.copy()

    # Yield control back to the test
    yield

    # Restore the original migrations list after the test
    global_migrations.clear()
    global_migrations.extend(original_migrations)


def test_multiple_migrations():
    class SimpleConfig(BaseModel):
        version: str

    class SimpleVectorizer(BaseModel):
        config: SimpleConfig

    # register some migrations
    def migration_func_1_2(old_vectorizer: SimpleVectorizer) -> dict[str, Any]:
        assert old_vectorizer.config.version == "0.0.1"
        old_vectorizer.config.version = "0.0.2"
        return old_vectorizer.model_dump()

    def migration_func_2_0_9(old_vectorizer: SimpleVectorizer) -> dict[str, Any]:
        assert old_vectorizer.config.version == "0.0.2"
        return {
            **vectorizer_fields,
            "config": config_0_9_0,
        }

    register_migration("0.0.2", SimpleVectorizer, "1 to 2")(migration_func_1_2)
    register_migration("0.9.0", SimpleVectorizer, "2 to 0.9.0")(migration_func_2_0_9)

    migreated_vectorizer = Vectorizer(
        **{  # type: ignore
            **vectorizer_fields,
            "config": config_0_10_0 | {"version": "0.0.1"},
        }
    )
    expected_vectorizer = Vectorizer(
        **{  # type: ignore
            **vectorizer_fields,
            "config": config_0_10_0 | {"original_version": "0.0.1"},
        }
    )

    assert migreated_vectorizer == expected_vectorizer


def test_migrate_config_from_ext_version_0_9_to_0_10():
    migrated_vectorizer = Vectorizer(
        **{  # type: ignore
            **vectorizer_fields,
            "config": config_0_9_0,
        }
    )  # pyright: ignore [reportArgumentType]
    expected_vectorizer = Vectorizer(
        **{  # type: ignore
            **vectorizer_fields,
            "config": config_0_10_0 | {"original_version": "0.9.0"},
        }
    )  # pyright: ignore [reportArgumentType]

    assert migrated_vectorizer == expected_vectorizer
