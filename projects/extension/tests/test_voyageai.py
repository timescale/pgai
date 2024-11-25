import os

import psycopg
import pytest


# skip tests in this module if disabled
enable_anthropic_tests = os.getenv("ENABLE_VOYAGEAI_TESTS")
if not enable_anthropic_tests or enable_anthropic_tests == "0":
    pytest.skip(allow_module_level=True)


@pytest.fixture()
def voyageai_api_key() -> str:
    voyageai_api_key = os.environ["VOYAGE_API_KEY"]
    return voyageai_api_key


@pytest.fixture()
def cur() -> psycopg.Cursor:
    with psycopg.connect("postgres://test@127.0.0.1:5432/test") as con:
        with con.cursor() as cur:
            yield cur


@pytest.fixture()
def cur_with_api_key(anthropic_api_key, cur) -> psycopg.Cursor:
    with cur:
        cur.execute(
            "select set_config('ai.voyage_api_key', %s, false) is not null",
            (anthropic_api_key,),
        )
        yield cur


def test_voyageai_embed(cur, voyageai_api_key):
    cur.execute(
        """
        select vector_dims
        (
            ai.voyageai_embed
            ( 'voyage-3-lite'
            , 'hello world'
            , api_key=>%s
            )
        )
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual == 512
