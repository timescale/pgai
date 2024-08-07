import os

import psycopg
import pytest


# skip tests in this module if disabled
enable_openai_tests = os.getenv("ENABLE_OPENAI_TESTS")
if not enable_openai_tests or enable_openai_tests == "0":
    pytest.skip(allow_module_level=True)


@pytest.fixture()
def openai_api_key() -> str:
    openai_api_key = os.environ["OPENAI_API_KEY"]
    return openai_api_key


@pytest.fixture()
def cur_with_api_key(openai_api_key, con) -> psycopg.Cursor:
    with con:
        with con.cursor() as cursor:
            cursor.execute(
                "select set_config('ai.openai_api_key', %s, false) is not null",
                (openai_api_key,),
            )
            yield cursor


def test_openai_list_models(cur, openai_api_key):
    cur.execute(
        """
        select count(*) > 0 as actual
        from ai.openai_list_models(_api_key=>%s)
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
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
            , _api_key=>%s
            )
        )
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
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
            , _api_key=>%s
            , _dimensions=>768
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
            , _dimensions=>768
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
            , _api_key=>%s
            , _user=>'bob'
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
            , _user=>'bob'
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
            , _api_key=>%s
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
          , _api_key=>%s
          ) as actual
        )
        select jsonb_extract_path_text(x.actual, 'choices', '0', 'message', 'content') is not null
        from x
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
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


def test_openai_moderate(cur, openai_api_key):
    cur.execute(
        """
        with x as
        (
            select ai.openai_moderate
            ( 'text-moderation-stable'
            , 'I want to kill them.'
            , _api_key=>%s
            ) as actual
        )
        select jsonb_extract_path_text(x.actual, 'results', '0', 'flagged')::bool
        from x
    """,
        (openai_api_key,),
    )
    actual = cur.fetchone()[0]
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
