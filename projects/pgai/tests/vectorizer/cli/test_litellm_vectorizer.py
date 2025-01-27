import json
import logging
import os
import re
from typing import Any

import pytest
from psycopg import Connection, sql
from psycopg.rows import dict_row

from tests.vectorizer.cli.conftest import (
    TestDatabase,
    configure_vectorizer,
    run_vectorizer_worker,
    setup_source_table,
)


@pytest.mark.parametrize(
    "num_items, concurrency, batch_size",
    [
        (1, 1, 1),
        (4, 2, 2),
    ],
)
@pytest.mark.parametrize(
    "embedding",
    [
        ("openai/text-embedding-3-small", 1536, {}, "OPENAI_API_KEY"),
        ("voyage/voyage-3-lite", 512, {}, "VOYAGE_API_KEY"),
        ("mistral/mistral-embed", 1024, {}, "MISTRAL_API_KEY"),
        ("cohere/embed-english-v3.0", 1024, {}, "COHERE_API_KEY"),
        (
            "huggingface/microsoft/codebert-base",
            768,
            {"wait_for_model": True, "use_cache": False},
            "HUGGINGFACE_API_KEY",
        ),
        (
            "azure/text-embedding-3-small",
            1536,
            {
                "api_base": os.getenv("AZURE_OPENAI_API_BASE"),
                "api_version": os.getenv("AZURE_OPENAI_API_VERSION"),
            },
            "AZURE_OPENAI_API_KEY",
        ),
    ],
)
def test_litellm_vectorizer(
    cli_db: tuple[TestDatabase, Connection],
    cli_db_url: str,
    embedding: tuple[str, int, dict[str, Any], str],
    num_items: int,
    concurrency: int,
    batch_size: int,
    vcr_: Any,
):
    model, dimensions, extra_options, api_key_name = embedding
    function = "embedding_litellm"

    if model == "huggingface/microsoft/codebert-base":
        pytest.skip("unable to get huggingface tests to reproduce reliably")

    if api_key_name not in os.environ:
        pytest.skip(f"environment variable '{api_key_name}' unset")

    embedding_str = f"{function}('{model}', {dimensions}, extra_options => '{json.dumps(extra_options)}'::jsonb)"  # noqa: E501 Line too long

    source_table = setup_source_table(cli_db[1], num_items)
    vectorizer_id = configure_vectorizer(
        source_table,
        connection=cli_db[1],
        concurrency=concurrency,
        batch_size=batch_size,
        embedding=embedding_str,
    )

    _, conn = cli_db
    # Insert pre-existing embedding for first item
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("""
           INSERT INTO
           blog_embedding_store(embedding_uuid, id, chunk_seq, chunk, embedding)
           VALUES (gen_random_uuid(), 1, 1, 'post_1',
            array_fill(0, ARRAY[{0}])::vector)
        """).format(dimensions)
        )

    stripped_model = re.sub(r"\W", "_", model)

    # When running the worker with cassette matching original test params
    cassette = f"{function}_{stripped_model}_{dimensions}_items_{num_items}_batch_size_{batch_size}.yaml"  # noqa: E501 Line too long
    logging.getLogger("vcr").setLevel(logging.DEBUG)
    with vcr_.use_cassette(cassette):
        result = run_vectorizer_worker(cli_db_url, vectorizer_id, concurrency)

    assert not result.exception
    assert result.exit_code == 0

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) as count FROM blog_embedding_store;")
        assert cur.fetchone()["count"] == num_items  # type: ignore
