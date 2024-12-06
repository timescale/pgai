import os

import psycopg
import pytest


# skip tests in this module if disabled
enable_anthropic_tests = os.getenv("ANTHROPIC_API_KEY")
if not enable_anthropic_tests or enable_anthropic_tests == "0":
    pytest.skip(allow_module_level=True)


@pytest.fixture()
def anthropic_api_key() -> str:
    anthropic_api_key = os.environ["ANTHROPIC_API_KEY"]
    return anthropic_api_key


@pytest.fixture()
def cur() -> psycopg.Cursor:
    with psycopg.connect("postgres://test@127.0.0.1:5432/test") as con:
        with con.cursor() as cur:
            yield cur


@pytest.fixture()
def cur_with_api_key(anthropic_api_key, cur) -> psycopg.Cursor:
    with cur:
        cur.execute(
            "select set_config('ai.anthropic_api_key', %s, false) is not null",
            (anthropic_api_key,),
        )
        yield cur


@pytest.fixture()
def cur_with_external_functions_executor_url(cur) -> psycopg.Cursor:
    with cur:
        cur.execute(
            "select set_config('ai.external_functions_executor_url', 'http://localhost:8000', false) is not null",
        )
        yield cur


def test_anthropic_generate(cur, anthropic_api_key):
    cur.execute(
        """
        with x as
        (
            select ai.anthropic_generate
            ( 'claude-3-5-sonnet-20240620'
            , jsonb_build_array
              ( jsonb_build_object
                ( 'role', 'user'
                , 'content', 'Name five famous people from Birmingham, Alabama.'
                )
              )
            , api_key=>%s
            ) as actual
        )
        select jsonb_extract_path_text(x.actual, 'content', '0', 'text') is not null 
            and x.actual->>'stop_reason' = 'end_turn'
        from x
    """,
        (anthropic_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual is True


def test_anthropic_generate_api_key_name(cur_with_external_functions_executor_url):
    cur_with_external_functions_executor_url.execute(
        """
        with x as
        (
            select ai.anthropic_generate
            ( 'claude-3-5-sonnet-20240620'
            , jsonb_build_array
              ( jsonb_build_object
                ( 'role', 'user'
                , 'content', 'Name five famous people from Birmingham, Alabama.'
                )
              )
            , api_key_name=> 'ANTHROPIC_API_KEY_REAL'
            ) as actual
        )
        select jsonb_extract_path_text(x.actual, 'content', '0', 'text') is not null 
            and x.actual->>'stop_reason' = 'end_turn'
        from x
    """
    )
    actual = cur_with_external_functions_executor_url.fetchone()[0]
    assert actual is True


def test_anthropic_generate_no_key(cur_with_api_key):
    cur_with_api_key.execute("""
        with x as
        (
            select ai.anthropic_generate
            ( 'claude-3-5-sonnet-20240620'
            , jsonb_build_array
              ( jsonb_build_object
                ( 'role', 'user'
                , 'content', 'Name five famous people from Birmingham, Alabama.'
                )
              )
            ) as actual
        )
        select jsonb_extract_path_text(x.actual, 'content', '0', 'text') is not null 
            and x.actual->>'stop_reason' = 'end_turn'
        from x
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual is True
