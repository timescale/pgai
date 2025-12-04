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
        psycopg.errors.InternalError_,
        match="missing VOYAGE_API_KEY secret",
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


def test_voyageai_embed_voyage_3_5_lite(cur, voyageai_api_key):
    """Test voyage-3.5-lite model (current naming)."""
    cur.execute(
        """
        select vector_dims
        (
            ai.voyageai_embed
            ( 'voyage-3.5-lite'
            , 'hello world'
            , api_key=>%s
            )
        )
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    # voyage-3.5-lite has 1024 dimensions by default
    assert actual == 1024


def test_voyageai_embed_voyage_3_5(cur, voyageai_api_key):
    """Test voyage-3.5 model."""
    cur.execute(
        """
        select vector_dims
        (
            ai.voyageai_embed
            ( 'voyage-3.5'
            , 'hello world'
            , api_key=>%s
            )
        )
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    # voyage-3.5 has 1024 dimensions by default
    assert actual == 1024


def test_voyageai_embed_voyage_3_large(cur, voyageai_api_key):
    """Test voyage-3-large model."""
    cur.execute(
        """
        select vector_dims
        (
            ai.voyageai_embed
            ( 'voyage-3-large'
            , 'hello world'
            , api_key=>%s
            )
        )
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    # voyage-3-large has 1024 dimensions by default
    assert actual == 1024


def test_voyageai_embed_with_output_dimension_256(cur, voyageai_api_key):
    """Test output_dimension parameter with 256 dimensions."""
    cur.execute(
        """
        select vector_dims
        (
            ai.voyageai_embed
            ( 'voyage-3-large'
            , 'hello world'
            , api_key=>%s
            , output_dimension=>256
            )
        )
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual == 256


def test_voyageai_embed_with_output_dimension_512(cur, voyageai_api_key):
    """Test output_dimension parameter with 512 dimensions."""
    cur.execute(
        """
        select vector_dims
        (
            ai.voyageai_embed
            ( 'voyage-3.5-lite'
            , 'hello world'
            , api_key=>%s
            , output_dimension=>512
            )
        )
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual == 512


def test_voyageai_embed_with_output_dimension_2048(cur, voyageai_api_key):
    """Test output_dimension parameter with 2048 dimensions."""
    cur.execute(
        """
        select vector_dims
        (
            ai.voyageai_embed
            ( 'voyage-3.5'
            , 'hello world'
            , api_key=>%s
            , output_dimension=>2048
            )
        )
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual == 2048


def test_voyageai_embed_output_dimension_with_multiple_inputs(cur, voyageai_api_key):
    """Test output_dimension works with multiple inputs."""
    cur.execute(
        """
        select count(*) from ai.voyageai_embed
        ( 'voyage-3-large'
        , ARRAY['hello world', 'goodbye world', 'test embedding']
        , api_key=>%s
        , output_dimension=>256
        )
    """,
        (voyageai_api_key,),
    )
    result = cur.fetchone()[0]
    assert result == 3


def test_voyageai_embed_with_output_dtype_float(cur, voyageai_api_key):
    """Test output_dtype parameter with float (default)."""
    cur.execute(
        """
        select vector_dims
        (
            ai.voyageai_embed
            ( 'voyage-3-large'
            , 'hello world'
            , api_key=>%s
            , output_dtype=>'float'
            )
        )
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual == 1024


def test_voyageai_embed_with_output_dtype_int8(cur, voyageai_api_key):
    """Test output_dtype parameter with int8 quantization."""
    cur.execute(
        """
        select vector_dims
        (
            ai.voyageai_embed
            ( 'voyage-3-large'
            , 'hello world'
            , api_key=>%s
            , output_dtype=>'int8'
            )
        )
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    # int8 still returns 1024 dimensions (quantized values converted to float for storage)
    assert actual == 1024


def test_voyageai_embed_with_output_dtype_uint8(cur, voyageai_api_key):
    """Test output_dtype parameter with uint8 quantization."""
    cur.execute(
        """
        select vector_dims
        (
            ai.voyageai_embed
            ( 'voyage-3.5-lite'
            , 'hello world'
            , api_key=>%s
            , output_dtype=>'uint8'
            )
        )
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual == 1024


def test_voyageai_embed_with_output_dtype_binary(cur, voyageai_api_key):
    """Test output_dtype parameter with binary quantization."""
    cur.execute(
        """
        select vector_dims
        (
            ai.voyageai_embed
            ( 'voyage-3-large'
            , 'hello world'
            , api_key=>%s
            , output_dimension=>1024
            , output_dtype=>'binary'
            )
        )
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    # binary returns 1024/8 = 128 packed integers, converted to float for storage
    assert actual == 128


def test_voyageai_embed_with_output_dtype_ubinary(cur, voyageai_api_key):
    """Test output_dtype parameter with ubinary quantization."""
    cur.execute(
        """
        select vector_dims
        (
            ai.voyageai_embed
            ( 'voyage-3.5'
            , 'hello world'
            , api_key=>%s
            , output_dimension=>512
            , output_dtype=>'ubinary'
            )
        )
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    # ubinary returns 512/8 = 64 packed integers
    assert actual == 64


def test_voyageai_embed_output_dtype_with_dimension(cur, voyageai_api_key):
    """Test output_dtype combined with output_dimension."""
    cur.execute(
        """
        select vector_dims
        (
            ai.voyageai_embed
            ( 'voyage-3-large'
            , 'hello world'
            , api_key=>%s
            , output_dimension=>256
            , output_dtype=>'int8'
            )
        )
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual == 256


def test_voyageai_rerank(cur, voyageai_api_key):
    """Test basic reranking functionality."""
    cur.execute(
        """
        with x as
        (
          select ai.voyageai_rerank
          ( 'rerank-2.5'
          , 'How long does it take for two programmers to work on something?'
          , array
            [ $$Good programmers don't just write programs. They build a working vocabulary.$$
            , 'One of the best programming skills you can have is knowing when to walk away for awhile.'
            , 'What one programmer can do in one month, two programmers can do in two months.'
            , 'how much wood would a woodchuck chuck if a woodchuck could chuck wood?'
            ]
          , api_key=>%s
          ) as actual
        )
        select y."index" as actual
        from x
        cross join lateral jsonb_to_recordset(x.actual->'results') y("index" int, relevance_score float8)
        order by y.relevance_score desc
        limit 1
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    # The document at index 2 is most relevant to the query
    assert actual == 2


def test_voyageai_rerank_with_top_k(cur, voyageai_api_key):
    """Test reranking with top_k parameter."""
    cur.execute(
        """
        with x as
        (
          select ai.voyageai_rerank
          ( 'rerank-2.5-lite'
          , 'programming best practices'
          , array
            [ $$Good programmers don't just write programs. They build a working vocabulary.$$
            , 'One of the best programming skills you can have is knowing when to walk away for awhile.'
            , 'What one programmer can do in one month, two programmers can do in two months.'
            , 'how much wood would a woodchuck chuck if a woodchuck could chuck wood?'
            ]
          , api_key=>%s
          , top_k=>2
          ) as actual
        )
        select jsonb_array_length(x.actual->'results') as result_count
        from x
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    # Should only return top 2 results
    assert actual == 2


def test_voyageai_rerank_simple(cur, voyageai_api_key):
    """Test simplified reranking interface."""
    cur.execute(
        """
        select x."index" as actual
        from ai.voyageai_rerank_simple
        ( 'rerank-2.5'
        , 'How long does it take for two programmers to work on something?'
        , array
          [ $$Good programmers don't just write programs. They build a working vocabulary.$$
          , 'One of the best programming skills you can have is knowing when to walk away for awhile.'
          , 'What one programmer can do in one month, two programmers can do in two months.'
          , 'how much wood would a woodchuck chuck if a woodchuck could chuck wood?'
          ]
        , api_key=>%s
        ) x
        order by relevance_score desc
        limit 1
    """,
        (voyageai_api_key,),
    )
    actual = cur.fetchone()[0]
    # The document at index 2 is most relevant
    assert actual == 2
