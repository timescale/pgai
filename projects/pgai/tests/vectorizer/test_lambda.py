from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import openai
import pytest
from psycopg import sql
from psycopg.rows import dict_row
from pydantic import ValidationError

from pgai.vectorizer.lambda_handler import lambda_handler

from . import expected
from .conftest import DIMENSION_COUNT, ItemFixture


def id_from_fixtures(request: pytest.FixtureRequest) -> str:
    embeddings = request.getfixturevalue("embedding")["implementation"]
    chunking = request.getfixturevalue("chunking")["implementation"]
    # Both will give us the same results for our small texts.
    if chunking.endswith("character_text_splitter"):
        chunking = "character_text_splitter"
    formatting = request.getfixturevalue("formatting")["implementation"]
    return f"{embeddings}-{chunking}-{formatting}"


def cassete_from_fixtures(request: pytest.FixtureRequest) -> str:
    items_count = len(request.getfixturevalue("items_fixtures"))
    batch_size = request.getfixturevalue("batch_size")
    return f"{id_from_fixtures(request)}-items={items_count}-batch_size={batch_size}"


@pytest.mark.usefixtures("db")
def test_handler_no_tasks_ok(event: dict[str, Any]):
    response = lambda_handler(event, None)
    expected_response = {"statusCode": 200, "processed_tasks": 0}
    assert expected_response == response


@pytest.mark.parametrize(
    ("items_fixtures", "concurrency", "batch_size"),
    [(1, 1, 1), (4, 2, 2)],
    indirect=["items_fixtures"],
)
def test_handler_ok(
    db_with_data: dict[str, Any],
    vcr_: Any,
    embedding_table_config: dict[str, Any],
    items_fixtures: list[ItemFixture],
    request: pytest.FixtureRequest,
    event: dict[str, Any],
):
    # Given some documents to be embedded.
    #
    # And one of the documents has an existing embeddings.
    with db_with_data["conn"].cursor() as cur:
        cur.execute(
            sql.SQL("INSERT INTO {}({}, {}, chunk_seq) VALUES (1, 1, 1) ").format(
                sql.Identifier(
                    embedding_table_config["target_schema"],
                    embedding_table_config["target_table"],
                ),
                sql.Identifier(embedding_table_config["source_pk"][0]["attname"]),
                sql.Identifier(embedding_table_config["source_pk"][1]["attname"]),
            ),
        )

    # When the lambda is invoked.
    with vcr_.use_cassette(f"{cassete_from_fixtures(request)}.yaml"):
        response = lambda_handler(event, None)

    # Then the lambda processes all documents.
    expected_response = {
        "statusCode": 200,
        "processed_tasks": len(items_fixtures),
    }
    assert expected_response == response

    with db_with_data["conn"].cursor(row_factory=dict_row) as cur:
        cur.execute(
            sql.SQL("SELECT * FROM {} ORDER BY {}, {}").format(
                sql.Identifier(
                    embedding_table_config["target_schema"],
                    embedding_table_config["target_table"],
                ),
                sql.Identifier(embedding_table_config["source_pk"][0]["attname"]),
                sql.Identifier(embedding_table_config["source_pk"][1]["attname"]),
            )
        )
        records = cur.fetchall()

        # And all the documents have a corresponding embedding.
        # Adn the existing embedding is no longer in the table.
        assert len(items_fixtures) == len(records)

        id_att = embedding_table_config["source_pk"][0]["attname"]
        id2_att = embedding_table_config["source_pk"][1]["attname"]

        # The fixtures are sorted by id as well so they should match the result
        # from the database.
        for i, record in enumerate(records):
            expected_item = items_fixtures[i]
            embedding = record.pop("embedding")
            chunk_id = record.pop("chunk_id")
            assert isinstance(chunk_id, UUID)
            assert record == {
                id_att: expected_item.pk_att_1,
                id2_att: expected_item.pk_att_2,
                "chunk": expected_item.content,
                "chunk_seq": 1,
            }

            assert (
                expected.embeddings[
                    f"{id_from_fixtures(request)}-{expected_item.pk_att_1}-{expected_item.pk_att_2}"
                ]
                == embedding
            )


def test_event_validation():
    event: dict[str, Any] = {}
    with pytest.raises(ValidationError):
        lambda_handler(event, None)


@pytest.mark.parametrize(
    ("chunking", "formatting", "embedding"),
    [("character_text_splitter", "chunk_value", "openai")],
    indirect=True,
)
def test_invalid_function_arguments(
    vcr_: Any,
    event: dict[str, Any],
    db_with_data: dict[str, Any],
):
    # Given an event with invalid arguments for the embedding model.
    event["payload"]["config"]["embedding"]["dimensions"] = DIMENSION_COUNT

    with (
        vcr_.use_cassette("test_invalid_function_arguments.yaml"),
        pytest.raises(openai.BadRequestError),
    ):
        # When the lambda is invokded.
        # Then it raises an exception.
        lambda_handler(event, None)

    # And an entry in the errors table is stored.
    with db_with_data["conn"].cursor(row_factory=dict_row) as cur:
        cur.execute(sql.SQL("SELECT * FROM ai.vectorizer_errors"))
        records = cur.fetchall()
        recorded = records[0].pop("recorded")
        assert datetime.now(timezone.utc) - recorded < timedelta(minutes=5)
        assert records == [
            {
                "id": 1,
                "message": "embedding provider failed",
                "details": {
                    "error_reason": "Error code: 400 - {'error': {'message': 'This model does not support specifying dimensions.', 'type': 'invalid_request_error', 'param': None, 'code': None}}",  # noqa: E501
                    "provider": "openai",
                },
            },
        ]


@pytest.mark.parametrize(
    ("items_fixtures", "batch_size", "chunking", "formatting"),
    [(2, 2, "recursive_character_text_splitter", "chunk_value")],
    indirect=["items_fixtures", "chunking", "formatting"],
)
def test_document_in_batch_exceeds_model_context_length(
    db_with_data: dict[str, Any],
    vcr_: Any,
    embedding_table_config: dict[str, Any],
    items_fixtures: list[ItemFixture],
    request: pytest.FixtureRequest,
    event: dict[str, Any],
):
    # Given two documents that will be embedded in the same batch.
    #
    # And one of the documents exceeds the models token length.
    with db_with_data["conn"].cursor() as cur:
        long_document = "AGI" * 5000
        cur.execute(
            sql.SQL("UPDATE {} SET content = %s WHERE {} = %s AND {} = %s").format(
                sql.Identifier(
                    embedding_table_config["source_schema"],
                    embedding_table_config["source_table"],
                ),
                sql.Identifier(embedding_table_config["source_pk"][0]["attname"]),
                sql.Identifier(embedding_table_config["source_pk"][1]["attname"]),
            ),
            (long_document, 2, 2),
        )

    # When the lambda is invoked.
    with vcr_.use_cassette("test_document_in_batch_too_long.yaml"):
        response = lambda_handler(event, None)

    # Then the lamda processes both documents.
    expected_response = {
        "statusCode": 200,
        "processed_tasks": 2,
    }
    assert expected_response == response

    with db_with_data["conn"].cursor(row_factory=dict_row) as cur:
        cur.execute(
            sql.SQL("SELECT * FROM {}").format(
                sql.Identifier(
                    embedding_table_config["target_schema"],
                    embedding_table_config["target_table"],
                ),
            )
        )
        records = cur.fetchall()

        id_att = embedding_table_config["source_pk"][0]["attname"]
        id2_att = embedding_table_config["source_pk"][1]["attname"]

        # And only the first document, which is withing the model's token
        # length is embedded.
        assert len(records) == 1
        record = records[0]
        expected_item = items_fixtures[0]
        embedding = record.pop("embedding")
        chunk_id = record.pop("chunk_id")
        assert isinstance(chunk_id, UUID)
        assert record == {
            id_att: expected_item.pk_att_1,
            id2_att: expected_item.pk_att_2,
            "chunk": expected_item.content,
            "chunk_seq": 1,
        }

        assert (
            expected.embeddings[
                f"{id_from_fixtures(request)}-{expected_item.pk_att_1}-{expected_item.pk_att_2}"
            ]
            == embedding
        )

        # And there's an error for the chunk that exceeded the model's context
        # length.
        cur.execute(sql.SQL("SELECT * FROM ai.vectorizer_errors").format())
        records = cur.fetchall()
        recorded = records[0].pop("recorded")
        assert datetime.now(timezone.utc) - recorded < timedelta(minutes=5)
        chunk = records[0]["details"].pop("chunk")
        assert chunk == expected.chunks["exceeds_model_context_length"]
        assert records == [
            {
                "details": {
                    "chunk_id": 1,
                    "error_reason": "chunk exceeds the text-embedding-ada-002 model context length of 8192 tokens",  # noqa
                    "pk": {
                        "id": 2,
                        "id2": 2,
                    },
                },
                "id": 1,
                "message": "chunk exceeds model context length",
            },
        ]


@pytest.mark.parametrize(
    ("items_fixtures", "batch_size", "chunking", "formatting"),
    [(2, 2, "recursive_character_text_splitter", "chunk_value")],
    indirect=["items_fixtures", "chunking", "formatting"],
)
def test_invalid_api_key_error(
    vcr_: Any,
    db_with_data: dict[str, Any],
    event: dict[str, Any],
):
    # Given two documents that will be embedded in the same batch.
    # And an event with an invalid API key.
    event["update_embeddings"]["secrets"]["OPENAI_API_KEY"] = "invalid"

    # When the lambda is invoked.
    # Then it returns an exception
    with (
        vcr_.use_cassette("test_invalid_api_key_error.yaml"),
        pytest.raises(openai.AuthenticationError),
    ):
        lambda_handler(event, None)

    # And there's an entry in the errors table for it.
    with db_with_data["conn"].cursor(row_factory=dict_row) as cur:
        cur.execute(sql.SQL("SELECT * FROM ai.vectorizer_errors"))
        records = cur.fetchall()
        recorded = records[0].pop("recorded")
        assert datetime.now(timezone.utc) - recorded < timedelta(minutes=5)
        assert records == [
            {
                "id": 1,
                "message": "embedding provider failed",
                "details": {
                    "provider": "openai",
                    "error_reason": "Error code: 401 - {'error': {'message': 'Incorrect API key provided: invalid. You can find your API key at https://platform.openai.com/account/api-keys.', 'type': 'invalid_request_error', 'param': None, 'code': 'invalid_api_key'}}",  # noqa: E501
                },
            },
        ]


@pytest.mark.parametrize(
    ("chunking", "formatting"),
    [("recursive_character_text_splitter", "chunk_value")],
    indirect=["chunking", "formatting"],
)
def test_no_api_key_error(
    base_event: dict[str, Any],
    embedding: dict[str, Any],
):
    # Given two documents that will be embedded in the same batch.
    # And an event without the required API key for the embeddings.
    api_key_name = embedding["api_key_name"]
    del base_event["update_embeddings"]["secrets"][api_key_name]

    # When the lambda is invoked.
    # Then it returns an exception
    with pytest.raises(ValueError, match=f"missing API key: {api_key_name}"):
        lambda_handler(base_event, None)
