import os

import psycopg
import pytest


# skip tests in this module if disabled
enable_voyageai_tests = os.getenv("VOYAGE_API_KEY")
if not enable_voyageai_tests or enable_voyageai_tests == "0":
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


def test_voyageai_fails_without_secret(cur, voyageai_api_key):
    with pytest.raises(
        psycopg.errors.InternalError_, match="missing VOYAGE_API_KEY secret"
    ) as _:
        cur.execute(
            """
            select vector_dims
            (
                ai.voyageai_embed
                ( 'voyage-3-lite'
                , 'hello world'
                )
            )
        """
        )


def test_voyageai_with_api_key_via_guc(cur, voyageai_api_key):
    cur.execute(
        "select set_config('ai.voyage_api_key', %s, false) is not null",
        (voyageai_api_key,),
    )
    cur.execute(
        """
        select vector_dims
        (
            ai.voyageai_embed
            ( 'voyage-3-lite'
            , 'hello world'
            )
        )
    """
    )
    actual = cur.fetchone()[0]
    assert actual == 512


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


def test_voyageai_embed_with_input_type(cur, voyageai_api_key):
    cur.execute(
        """
        select ai.voyageai_embed
        ( 'voyage-3-lite'
        , 'hello world'
        , api_key=>%s
        , input_type => 'document'
        )
    """,
        (voyageai_api_key,),
    )
    document = cur.fetchone()[0]
    cur.execute(
        """
        select ai.voyageai_embed
        ( 'voyage-3-lite'
        , 'hello world'
        , api_key=>%s
        , input_type => 'query'
        )
    """,
        (voyageai_api_key,),
    )
    query = cur.fetchone()[0]
    # Note: embeddings may not be deterministic, so asserting that the vectors
    # are not equal may be a red herring. I did check that two embeddings with
    # `input_type => 'document'` are the same, but this may not hold in the
    # future.
    assert query != document


def test_voyageai_embed_successful_with_very_large_input(cur, voyageai_api_key):
    cur.execute(
        """
        select vector_dims
        (
            ai.voyageai_embed
            ( 'voyage-3-lite'
            , repeat('hello world', 20000)
            , api_key=>%s
            )
        )
    """,
        (voyageai_api_key,),
    )
    dims = cur.fetchone()[0]
    assert dims == 512


def test_voyageai_embed_with_multiple_inputs(cur, voyageai_api_key):
    cur.execute(
        """
            select count(*) from ai.voyageai_embed
            ( 'voyage-3-lite'
            , ARRAY['hello world', 'hello bob']
            , api_key=>%s
            )
    """,
        (voyageai_api_key,),
    )
    result = cur.fetchone()[0]
    assert result == 2
