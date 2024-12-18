import os
from typing import List

import psycopg
import pytest


@pytest.fixture()
def cur() -> psycopg.Cursor:
    with psycopg.connect("postgres://test@127.0.0.1:5432/test") as con:
        with con.cursor() as cur:
            yield cur


models = [
    {
        "id": "openai",
        "name": "openai/text-embedding-3-small",
        "dimensions": 1536,
        "api_key_name": "OPENAI_API_KEY",
        "exception": "OpenAIException - The api_key client option must be set",
        "input_types": [],
    },
    {
        "id": "voyage",
        "name": "voyage/voyage-3-lite",
        "dimensions": 512,
        "api_key_name": "VOYAGE_API_KEY",
        "exception": "VoyageException - The api_key client option must be set",
        "input_types": ["query", "document"],
    },
    {
        "id": "cohere",
        "name": "cohere/embed-english-v3.0",
        "dimensions": 1024,
        "api_key_name": "COHERE_API_KEY",
        "exception": """CohereException - {"message":"no api key supplied"}""",
        "input_types": [
            "search_query",
            "search_document",
            "classification",
            "clustering",
        ],
    },
    {
        "id": "mistral",
        "name": "mistral/mistral-embed",
        "dimensions": 1024,
        "api_key_name": "MISTRAL_API_KEY",
        "exception": "MistralException - The api_key client option must be set",
        "input_types": [],
    },
    {
        "id": "huggingface",
        "name": "huggingface/microsoft/codebert-base",
        "dimensions": 768,
        "api_key_name": "HUGGINGFACE_API_KEY",
        "exception": """HuggingfaceException - {"error":"Please log in or use a HF access token"}""",
        "input_types": [],
    },
]

ids = [model["id"] for model in models]


def model_keys(*args):
    return [[i[k] for k in args] for i in models]


@pytest.mark.parametrize("name,exception", model_keys("name", "exception"), ids=ids)
def test_litellm_embed_fails_without_secret(
    cur: psycopg.Cursor, name: str, exception: str
):
    with pytest.raises(psycopg.errors.ExternalRoutineException, match=exception) as _:
        cur.execute(
            """
            select vector_dims
            (
                ai.litellm_embed
                ( %s
                , 'hello world'
                )
            )
        """,
            (name,),
        )


@pytest.mark.parametrize(
    "name,dimensions,api_key_name",
    model_keys("name", "dimensions", "api_key_name"),
    ids=ids,
)
def test_litellm_embed_with_api_key_via_guc(
    cur: psycopg.Cursor, name: str, dimensions: int, api_key_name: str
):
    api_key_value = os.getenv(api_key_name)
    if api_key_value is None:
        pytest.skip(f"environment variable '{api_key_name}' unset")
    cur.execute(
        f"select set_config('ai.{api_key_name.lower()}', %s, false) is not null",
        (api_key_value,),
    )
    cur.execute(
        """
        select vector_dims
        (
            ai.litellm_embed
            ( %s
            , 'hello world'
            , api_key_name => %s
            )
        )
    """,
        (
            name,
            api_key_name,
        ),
    )
    actual = cur.fetchone()[0]
    assert actual == dimensions


@pytest.mark.parametrize(
    "name,dimensions,api_key_name",
    model_keys("name", "dimensions", "api_key_name"),
    ids=ids,
)
def test_litellm_embed(
    cur: psycopg.Cursor, name: str, dimensions: int, api_key_name: str
):
    api_key_value = os.getenv(api_key_name)
    if api_key_value is None:
        pytest.skip(f"environment variable '{api_key_name}' unset")
    cur.execute(
        """
        select vector_dims
        (
            ai.litellm_embed
            ( %s
            , 'hello world'
            , api_key=>%s
            )
        )
        """,
        (
            name,
            api_key_value,
        ),
    )
    actual = cur.fetchone()[0]
    assert actual == dimensions


@pytest.mark.parametrize(
    "name,dimensions,api_key_name,input_types",
    model_keys("name", "dimensions", "api_key_name", "input_types"),
    ids=ids,
)
def test_litellm_embed_input_types(
    cur: psycopg.Cursor,
    name: str,
    dimensions: int,
    api_key_name: str,
    input_types: List[str],
):
    api_key_value = os.getenv(api_key_name)
    if api_key_value is None:
        pytest.skip(f"environment variable '{api_key_name}' unset")
    if len(input_types) == 0:
        pytest.skip("no input types for model")
    for input_type in input_types:
        cur.execute(
            """
            select vector_dims
            (
                ai.litellm_embed
                ( %s
                , 'hello world'
                , api_key=>%s
                , extra_options => jsonb_build_object('input_type', %s::text)
                )
            )
            """,
            (
                name,
                api_key_value,
                input_type,
            ),
        )
        actual = cur.fetchone()[0]
        assert actual == dimensions


@pytest.mark.parametrize(
    "name,dimensions,api_key_name",
    model_keys("name", "dimensions", "api_key_name"),
    ids=ids,
)
def test_litellm_embed_with_multiple_inputs(
    cur: psycopg.Cursor, name: str, dimensions: int, api_key_name: str
):
    api_key_value = os.getenv(api_key_name)
    if api_key_value is None:
        pytest.skip(f"environment variable '{api_key_name}' unset")
    cur.execute(
        """
            select count(*) from ai.litellm_embed
            ( %s
            , ARRAY['hello world', 'hello bob']
            , api_key=>%s
            )
        """,
        (
            name,
            api_key_value,
        ),
    )
    result = cur.fetchone()[0]
    assert result == 2


def load_secrets(*args):
    secrets = {}
    for name in args:
        secrets[name] = os.getenv(name)
        if secrets[name] is None:
            pytest.skip(f"environment variable '{name}' unset")
    return secrets


def test_litellm_embed_azure_openai(cur: psycopg.Cursor):
    secrets = load_secrets(
        "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_API_BASE", "AZURE_OPENAI_API_VERSION"
    )
    cur.execute(
        """
        select vector_dims
        (
            ai.litellm_embed
            ( 'azure/text-embedding-3-small'
            , 'hello world'
            , api_key=> %s
            , extra_options => jsonb_build_object(
                'api_base', %s::text,
                'api_version', %s::text
              )
            )
        )
        """,
        (
            secrets["AZURE_OPENAI_API_KEY"],
            secrets["AZURE_OPENAI_API_BASE"],
            secrets["AZURE_OPENAI_API_VERSION"],
        ),
    )
    actual = cur.fetchone()[0]
    assert actual == 1536


def test_litellm_embed_bedrock(cur: psycopg.Cursor):
    secrets = load_secrets(
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION_NAME"
    )
    cur.execute(
        """
        select vector_dims
        (
            ai.litellm_embed
            ( 'amazon.titan-embed-text-v1'
            , 'hello world'
            , extra_options => jsonb_build_object(
                'aws_access_key_id', %s::text,
                'aws_secret_access_key', %s::text,
                'aws_region_name', %s::text
              )
            )
        )
        """,
        (
            secrets["AWS_ACCESS_KEY_ID"],
            secrets["AWS_SECRET_ACCESS_KEY"],
            secrets["AWS_REGION_NAME"],
        ),
    )
    actual = cur.fetchone()[0]
    assert actual == 1536


@pytest.mark.skip(reason="testing vertex is hard")
def test_litellm_embed_vertex_ai(cur: psycopg.Cursor):
    secrets = load_secrets("VERTEX_CREDENTIALS")
    cur.execute(
        """
        select vector_dims
        (
            ai.litellm_embed
            ( 'vertex_ai/textembedding-gecko'
            , 'hello world'
            , extra_options => jsonb_build_object(
                'vertex_credentials', %s::text,
                'vertex_project', 'sandbox-james',
                'vertex_location', 'us-central1'
              )
            )
        )
        """,
        (secrets["VERTEX_CREDENTIALS"],),
    )
    actual = cur.fetchone()[0]
    assert actual == 768
