import os

import psycopg
import pytest

# skip tests in this module if disabled
enable_openai_tests = os.getenv("OPENAI_API_KEY")
if not enable_openai_tests or enable_openai_tests == "0":
    pytest.skip(allow_module_level=True)


@pytest.fixture()
def openai_api_key() -> str:
    openai_api_key = os.environ["OPENAI_API_KEY"]
    return openai_api_key


@pytest.fixture()
def cur() -> psycopg.Cursor:
    with psycopg.connect("postgres://test@127.0.0.1:5432/test") as con:
        with con.cursor() as cur:
            yield cur


@pytest.fixture()
def cur_with_api_key(openai_api_key, cur) -> psycopg.Cursor:
    with cur:
        cur.execute(
            "select set_config('ai.openai_api_key', %s, false) is not null",
            (openai_api_key,),
        )
        yield cur


@pytest.fixture()
def cur_with_external_functions_executor_url(cur) -> psycopg.Cursor:
    with cur:
        cur.execute(
            "select set_config('ai.external_functions_executor_url', 'http://0.0.0.0:8000', false) is not null",
        )
        yield cur


def test_openai_list_models(cur, openai_api_key):
    cur.execute(
        """
        select count(*) > 0 as actual
        from ai.openai_list_models(
            api_key=>%s,
            extra_headers=>'{"X-Custom-Header": "my-value"}',
            extra_query=>'{"debug": true}'
        )
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual > 0


def test_openai_list_models_with_raw_response(cur, openai_api_key):
    cur.execute(
        """
        select ai.openai_list_models_with_raw_response(
            api_key=>%s,
            extra_headers=>'{"X-Custom-Header": "my-value"}',
            extra_query=>'{"debug": true}'
        )
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert len(actual["data"]) > 0
    assert actual["object"] == "list"


def test_openai_list_models_api_key_name(cur_with_external_functions_executor_url):
    cur_with_external_functions_executor_url.execute(
        """
        select count(*) > 0 as actual
        from ai.openai_list_models(api_key_name=> 'OPENAI_API_KEY_REAL')
    """
    )
    actual = cur_with_external_functions_executor_url.fetchone()[0]
    assert actual > 0


def test_openai_list_models_no_key(cur_with_api_key):
    cur_with_api_key.execute("""
        select count(*) > 0 as actual
        from ai.openai_list_models()
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual > 0


def test_openai_tokenize(cur):
    cur.execute("""
        select ai.openai_tokenize('text-embedding-ada-002', 'the purple elephant sits on a red mushroom')::text as actual
    """)
    actual = cur.fetchone()[0]
    assert actual == "{1820,25977,46840,23874,389,264,2579,58466}"


def test_openai_detokenize(cur):
    cur.execute("""
        select ai.openai_detokenize('text-embedding-ada-002', array[1820,25977,46840,23874,389,264,2579,58466]) as actual
    """)
    actual = cur.fetchone()[0]
    assert actual == "the purple elephant sits on a red mushroom"


def test_openai_embed(cur, openai_api_key):
    cur.execute(
        """
        select vector_dims
        (
            ai.openai_embed
            ( 'text-embedding-ada-002'
            , 'the purple elephant sits on a red mushroom'
            , api_key=>%s
            , extra_headers=>'{"X-Custom-Header": "my-value"}'
            , extra_query=>'{"debug": true}'
            )
        )
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual == 1536


def test_openai_embed_with_raw_response(cur, openai_api_key):
    cur.execute(
        """
        select ai.openai_embed_with_raw_response
            ( 'text-embedding-ada-002'
            , 'the purple elephant sits on a red mushroom'
            , api_key=>%s
            , extra_headers=>'{"X-Custom-Header": "my-value"}'
            , extra_query=>'{"debug": true}'
            )
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    embedding = actual["data"][0].pop("embedding")
    assert actual == {
        "data": [
            {
                "index": 0,
                "object": "embedding",
            },
        ],
        "model": "text-embedding-ada-002-v2",
        "object": "list",
        "usage": {
            "prompt_tokens": 8,
            "total_tokens": 8,
        },
    }
    assert len(embedding) == 8192


@pytest.mark.parametrize(
    "model,max_tokens,stopped,error_str",
    [
        # OK.
        ("o1", {"max_completion_tokens": 10000}, False, None),
        # Stopped generating because max_tokens was reached.
        ("o1", {"max_completion_tokens": 100}, True, None),
        # 400 status code is returned because not enough tokens for generation.
        (
            "o1",
            {"max_completion_tokens": 1},
            None,
            "Could not finish the message because max_tokens",
        ),
        # Stopped generating because max_tokens was reached.
        ("o3-mini", {"max_completion_tokens": 10000}, False, None),  # OK.
        (
            "o3-mini",
            {"max_completion_tokens": 100},
            True,
            None,
        ),
        # 400 status code is returned because not enough tokens for generation.
        (
            "o3-mini",
            {"max_completion_tokens": 1},
            None,
            "Could not finish the message because max_tokens",
        ),
        # starting from o1, all reasoning models (o*) deprecated the max_tokens parameter in favor of max_completion_tokens
        # see https://platform.openai.com/docs/guides/reasoning#controlling-costs
        (
            "o3-mini",
            {"max_tokens": 1},
            None,
            "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead.",
        ),
    ],
)
def test_openai_chat_complete_with_tokens_limitation_on_reasoning_models(
    cur, openai_api_key, model, max_tokens, stopped, error_str
):
    query = f"""
        with x as
        (
          select ai.openai_chat_complete
          ( %(model)s
          , jsonb_build_array
            ( jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
            )
          , api_key=>%(api_key)s
          , extra_query=>'{{"debug": true}}'
          {', max_tokens=>' + str(max_tokens.get("max_tokens")) if max_tokens.get("max_tokens") else ''}
          {', max_completion_tokens=>' + str(max_tokens.get("max_completion_tokens")) if max_tokens.get("max_completion_tokens") else ''}
          ) as actual
        )
        select
            jsonb_extract_path_text(x.actual, 'choices', '0', 'message', 'content'),
            jsonb_extract_path_text(x.actual, 'choices', '0', 'finish_reason')
        from x
    """
    params = {"model": model, "api_key": openai_api_key}

    if error_str:
        with pytest.raises(psycopg.errors.ExternalRoutineException) as exception_raised:
            cur.execute(query, params)

        assert error_str in str(
            exception_raised.value
        ), f"expected {error_str} in {str(exception_raised.value)}"
    else:
        cur.execute(query, params)
        actual = cur.fetchone()
        content = actual[0]
        finish_reason = actual[1]

        if stopped:
            assert finish_reason == "length"
            # assert len(content) == 0 have experienced issues with this line. sometimes content is returned
        else:
            assert len(content) > 0


def test_openai_embed_api_key_name(cur_with_external_functions_executor_url):
    cur_with_external_functions_executor_url.execute(
        """
        select vector_dims
        (
            ai.openai_embed
            ( 'text-embedding-ada-002'
            , 'the purple elephant sits on a red mushroom'
            , api_key_name=> 'OPENAI_API_KEY_REAL'
            )
        )
    """
    )
    actual = cur_with_external_functions_executor_url.fetchone()[0]
    assert actual == 1536


def test_openai_embed_no_key(cur_with_api_key):
    cur_with_api_key.execute("""
        select vector_dims
        (
            ai.openai_embed
            ( 'text-embedding-ada-002'
            , 'the purple elephant sits on a red mushroom'
            )
        )
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual == 1536


def test_openai_embed_2(cur, openai_api_key):
    cur.execute(
        """
        select vector_dims
        (
            ai.openai_embed
            ( 'text-embedding-3-large'
            , 'the purple elephant sits on a red mushroom'
            , api_key=>%s
            , dimensions=>768
            )
        )
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual == 768


def test_openai_embed_2_no_key(cur_with_api_key):
    cur_with_api_key.execute("""
        select vector_dims
        (
            ai.openai_embed
            ( 'text-embedding-3-large'
            , 'the purple elephant sits on a red mushroom'
            , dimensions=>768
            )
        )
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual == 768


def test_openai_embed_3(cur, openai_api_key):
    cur.execute(
        """
        select vector_dims
        (
            ai.openai_embed
            ( 'text-embedding-3-large'
            , 'the purple elephant sits on a red mushroom'
            , api_key=>%s
            , openai_user=>'bob'
            )
        )
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual == 3072


def test_openai_embed_3_no_key(cur_with_api_key):
    cur_with_api_key.execute("""
        select vector_dims
        (
            ai.openai_embed
            ( 'text-embedding-3-large'
            , 'the purple elephant sits on a red mushroom'
            , openai_user=>'bob'
            )
        )
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual == 3072


def test_openai_embed_array_of_text(cur_with_api_key):
    cur_with_api_key.execute("""
        select sum(vector_dims(embedding)) as actual
        from ai.openai_embed
        ( 'text-embedding-3-large'
        , array['the purple elephant sits on a red mushroom', 'timescale is postgres made powerful']
        )
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual == 6144


def test_openai_embed_array_of_text_with_raw_response(cur, openai_api_key):
    cur.execute(
        """
        select ai.openai_embed_with_raw_response
            ( 'text-embedding-ada-002'
            , array['the purple elephant sits on a red mushroom', 'timescale is postgres made powerful']
            , api_key=>%s
            , extra_headers=>'{"X-Custom-Header": "my-value"}'
            , extra_query=>'{"debug": true}'
            )
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    embeddings = actual["data"]
    for embedding_result in embeddings:
        embedding = embedding_result.pop("embedding")
        assert len(embedding) == 8192

    assert actual == {
        "data": [
            {
                "index": 0,
                "object": "embedding",
            },
            {
                "index": 1,
                "object": "embedding",
            },
        ],
        "model": "text-embedding-ada-002-v2",
        "object": "list",
        "usage": {
            "prompt_tokens": 14,
            "total_tokens": 14,
        },
    }


def test_openai_embed_array_of_tokens(cur, openai_api_key):
    cur.execute(
        """
        select vector_dims
        (
            ai.openai_embed
            ( 'text-embedding-ada-002'
            , array[1820,25977,46840,23874,389,264,2579,58466]
            , api_key=>%s
            )
        )
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual == 1536


def test_openai_embed_array_of_tokens_with_raw_response(cur, openai_api_key):
    cur.execute(
        """
        select ai.openai_embed_with_raw_response
            ( 'text-embedding-ada-002'
            , array[1820,25977,46840,23874,389,264,2579,58466]
            , api_key=>%s
            )
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    embedding = actual["data"][0].pop("embedding")
    assert actual == {
        "data": [
            {
                "index": 0,
                "object": "embedding",
            },
        ],
        "model": "text-embedding-ada-002-v2",
        "object": "list",
        "usage": {
            "prompt_tokens": 8,
            "total_tokens": 8,
        },
    }
    assert len(embedding) == 8192


def test_openai_embed_5_no_key(cur_with_api_key):
    cur_with_api_key.execute("""
        select vector_dims
        (
            ai.openai_embed
            ( 'text-embedding-ada-002'
            , array[1820,25977,46840,23874,389,264,2579,58466]
            )
        )
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual == 1536


def test_openai_chat_complete(cur, openai_api_key):
    cur.execute(
        """
        with x as
        (
          select ai.openai_chat_complete
          ( 'gpt-4o'
          , jsonb_build_array
            ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
            , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
            )
          , api_key=>%s
          , extra_headers=>'{"X-Custom-Header": "my-value"}'
          , extra_query=>'{"debug": true}'
          ) as actual
        )
        select jsonb_extract_path_text(x.actual, 'choices', '0', 'message', 'content') is not null
        from x
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual is True


def test_openai_chat_complete_with_raw_response(cur, openai_api_key):
    cur.execute(
        """
        select ai.openai_chat_complete_with_raw_response
          ( 'gpt-4o'
          , jsonb_build_array
            ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
            , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
            )
          , api_key=>%s
          , extra_headers=>'{"X-Custom-Header": "my-value"}'
          , extra_query=>'{"debug": true}'
          ) as actual
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert len(actual["choices"][0]["message"]) > 0
    assert actual["object"] == "chat.completion"


def test_openai_chat_complete_api_key_name(cur_with_external_functions_executor_url):
    cur_with_external_functions_executor_url.execute(
        """
        with x as
        (
          select ai.openai_chat_complete
          ( 'gpt-4o'
          , jsonb_build_array
            ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
            , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
            )
          , api_key_name=> 'OPENAI_API_KEY_REAL'
          ) as actual
        )
        select jsonb_extract_path_text(x.actual, 'choices', '0', 'message', 'content') is not null
        from x
    """
    )
    actual = cur_with_external_functions_executor_url.fetchone()[0]
    assert actual is True


def test_openai_chat_complete_no_key(cur_with_api_key):
    cur_with_api_key.execute("""
        with x as
        (
          select ai.openai_chat_complete
          ( 'gpt-4o'
          , jsonb_build_array
            ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
            , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
            )
          ) as actual
        )
        select jsonb_extract_path_text(x.actual, 'choices', '0', 'message', 'content') is not null
        from x
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual is True


def test_openai_chat_complete_simple(cur, openai_api_key):
    cur.execute(
        """
        with x as
        (
            select ai.openai_chat_complete_simple('what is the typical weather like in Alabama in June', api_key=>%s) as actual
        )
        select x.actual is not null
        from x
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual is True


def test_openai_chat_complete_simple_no_key(cur_with_api_key):
    cur_with_api_key.execute("""
        with x as
        (
            select ai.openai_chat_complete_simple('what is the typical weather like in Alabama in June') as actual
        )
        select x.actual is not null
        from x
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual is True


def test_openai_moderate(cur, openai_api_key):
    cur.execute(
        """
        with x as
        (
            select ai.openai_moderate
            ( 'omni-moderation-latest'
            , 'I want to kill them.'
            , api_key=>%s
            , extra_headers=>'{"X-Custom-Header": "my-value"}'
            , extra_query=>'{"debug": true}'
            ) as actual
        )
        select jsonb_extract_path_text(x.actual, 'results', '0', 'flagged')::bool
        from x
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual is True


def test_openai_moderate_with_raw_response(cur, openai_api_key):
    cur.execute(
        """
        select ai.openai_moderate
        ( 'omni-moderation-latest'
        , 'I want to kill them.'
        , api_key=>%s
        , extra_headers=>'{"X-Custom-Header": "my-value"}'
        , extra_query=>'{"debug": true}'
        ) as actual
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual["results"][0]["flagged"] is True


def test_openai_moderate_api_key_name(cur_with_external_functions_executor_url):
    cur_with_external_functions_executor_url.execute(
        """
        with x as
        (
            select ai.openai_moderate
            ( 'omni-moderation-latest'
            , 'I want to kill them.'
            , api_key_name=> 'OPENAI_API_KEY_REAL'
            ) as actual
        )
        select jsonb_extract_path_text(x.actual, 'results', '0', 'flagged')::bool
        from x
    """
    )
    actual = cur_with_external_functions_executor_url.fetchone()[0]
    assert actual is True


def test_openai_moderate_no_key(cur_with_api_key):
    cur_with_api_key.execute("""
        with x as
        (
            select ai.openai_moderate
            ( 'omni-moderation-latest'
            , 'I want to kill them.'
            ) as actual
        )
        select jsonb_extract_path_text(x.actual, 'results', '0', 'flagged')::bool
        from x
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual is True


def test_openai_client_config(cur):
    cur.execute("""
        select ai.openai_client_config(
            timeout_seconds => 0.1,
            max_retries => 1,
            organization => 'my-org',
            project => 'my-project',
            default_headers => '{"X-Custom-Header": "my-value"}',
            default_query => '{"debug": "true"}',
            base_url => 'http://api.com'
        )
    """)
    actual = cur.fetchone()[0]
    assert actual == {
        "base_url": "http://api.com",
        "default_headers": {
            "X-Custom-Header": "my-value",
        },
        "default_query": {
            "debug": "true",
        },
        "max_retries": 1,
        "organization": "my-org",
        "project": "my-project",
        "timeout": 0.1,
    }


def test_openai_client_config_timeout(cur_with_api_key):
    with pytest.raises(psycopg.errors.ExternalRoutineException) as exc_info:
        cur_with_api_key.execute("""
            select ai.openai_embed(
                'text-embedding-ada-002',
                'the purple elephant sits on a red mushroom',
                client_config => ai.openai_client_config(
                    timeout_seconds => 0.1,
                    max_retries => 1
                )
            )
        """)
        cur_with_api_key.fetchone()
    assert "Request timed out" in str(exc_info.value)


def test_openai_client_config_base_url(cur_with_api_key):
    with pytest.raises(psycopg.errors.ExternalRoutineException) as exc_info:
        cur_with_api_key.execute("""
            select ai.openai_embed(
                'text-embedding-ada-002',
                'the purple elephant sits on a red mushroom',
                client_config => ai.openai_client_config(
                    max_retries => 1,
                    base_url => 'http://not-an-api-asdf1234.com'
                )
            )
        """)
        cur_with_api_key.fetchone()
    assert "openai.APIConnectionError: Connection error" in str(exc_info.value)
