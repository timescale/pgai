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
            "select set_config('ai.external_functions_executor_url', 'http://localhost:8000', false) is not null",
        )
        yield cur


def test_openai_list_models(cur, openai_api_key):
    cur.execute(
        """
        select count(*) > 0 as actual
        from ai.openai_list_models(api_key=>%s)
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual > 0


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
            )
        )
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual == 1536


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


def test_openai_embed_4(cur_with_api_key):
    cur_with_api_key.execute("""
        select sum(vector_dims(embedding)) as actual
        from ai.openai_embed
        ( 'text-embedding-3-large'
        , array['the purple elephant sits on a red mushroom', 'timescale is postgres made powerful']
        )
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual == 6144


def test_openai_embed_5(cur, openai_api_key):
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
          ) as actual
        )
        select jsonb_extract_path_text(x.actual, 'choices', '0', 'message', 'content') is not null
        from x
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual is True


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
            ( 'text-moderation-stable'
            , 'I want to kill them.'
            , api_key=>%s
            ) as actual
        )
        select jsonb_extract_path_text(x.actual, 'results', '0', 'flagged')::bool
        from x
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual is True


def test_openai_moderate_api_key_name(cur_with_external_functions_executor_url):
    cur_with_external_functions_executor_url.execute(
        """
        with x as
        (
            select ai.openai_moderate
            ( 'text-moderation-stable'
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
            ( 'text-moderation-stable'
            , 'I want to kill them.'
            ) as actual
        )
        select jsonb_extract_path_text(x.actual, 'results', '0', 'flagged')::bool
        from x
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual is True
