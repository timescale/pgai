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
            "config": config_0_10_0,
        }
    )  # pyright: ignore [reportArgumentType]

    migrated_vectorizer.config.version = (
        "0.10.0"  # The version field is not adapted, for comparison we set it manually
    )
    assert migrated_vectorizer == expected_vectorizer
