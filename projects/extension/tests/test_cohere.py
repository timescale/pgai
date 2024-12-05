import os

import psycopg
import pytest


# skip tests in this module if disabled
enable_cohere_tests = os.getenv("COHERE_API_KEY")
if not enable_cohere_tests or enable_cohere_tests == "0":
    pytest.skip(allow_module_level=True)


@pytest.fixture()
def cohere_api_key() -> str:
    cohere_api_key = os.environ["COHERE_API_KEY"]
    return cohere_api_key


@pytest.fixture()
def cur() -> psycopg.Cursor:
    with psycopg.connect("postgres://test@127.0.0.1:5432/test") as con:
        with con.cursor() as cur:
            yield cur


@pytest.fixture()
def cur_with_api_key(cohere_api_key, cur) -> psycopg.Cursor:
    with cur:
        cur.execute(
            "select set_config('ai.cohere_api_key', %s, false) is not null",
            (cohere_api_key,),
        )
        yield cur


@pytest.fixture()
def cur_with_external_functions_executor_url(cur) -> psycopg.Cursor:
    with cur:
        cur.execute(
            "select set_config('ai.external_functions_executor_url', 'http://localhost:8000', false) is not null",
        )
        yield cur


def test_cohere_list_models(cur, cohere_api_key):
    cur.execute(
        """
        select count(*) > 0
        from ai.cohere_list_models(api_key=>%s)
    """,
        (cohere_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual is True


def test_cohere_list_models_no_key(cur_with_api_key):
    cur_with_api_key.execute("""
        select count(*) > 0
        from ai.cohere_list_models()
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual is True


def test_cohere_list_models_endpoint(cur_with_api_key):
    cur_with_api_key.execute("""
        select count(*) > 0
        from ai.cohere_list_models(endpoint=>'embed')
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual is True


def test_cohere_tokenize(cur, cohere_api_key):
    cur.execute(
        """
        select array_length
        (
            ai.cohere_tokenize
            ( 'command'
            , 'What one programmer can do in one month, two programmers can do in two months.'
            , api_key=>%s
            )
        , 1
        )
    """,
        (cohere_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual == 17


def test_cohere_tokenize_api_key_name(cur_with_external_functions_executor_url):
    cur_with_external_functions_executor_url.execute(
        """
        select array_length
        (
            ai.cohere_tokenize
            ( 'command'
            , 'What one programmer can do in one month, two programmers can do in two months.'
            , api_key_name=> 'COHERE_API_KEY_REAL'
            )
        , 1
        )
    """
    )
    actual = cur_with_external_functions_executor_url.fetchone()[0]
    assert actual == 17


def test_cohere_tokenize_no_key(cur_with_api_key):
    cur_with_api_key.execute("""
        select ai.cohere_tokenize
        ( 'command'
        , 'One of the best programming skills you can have is knowing when to walk away for awhile.'
        )::text
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert (
        actual
        == "{5256,1707,1682,2383,9461,4696,1739,1863,1871,1740,9397,2112,1705,4066,3465,1742,38700,21}"
    )


def test_cohere_detokenize(cur, cohere_api_key):
    cur.execute(
        """
        select ai.cohere_detokenize
        ( 'command'
        , array[5171,2011,36613,1863,1978,1703,2011,2812,19,2253,38374,1863,1978,1703,2253,3784,21]
        , api_key=>%s
        )
    """,
        (cohere_api_key,),
    )
    actual = cur.fetchone()[0]
    assert (
        actual
        == "What one programmer can do in one month, two programmers can do in two months."
    )


def test_cohere_detokenize_api_key_name(cur_with_external_functions_executor_url):
    cur_with_external_functions_executor_url.execute(
        """
        select ai.cohere_detokenize
        ( 'command'
        , array[5171,2011,36613,1863,1978,1703,2011,2812,19,2253,38374,1863,1978,1703,2253,3784,21]
        , api_key_name=> 'COHERE_API_KEY_REAL'
        )
    """
    )
    actual = cur_with_external_functions_executor_url.fetchone()[0]
    assert (
        actual
        == "What one programmer can do in one month, two programmers can do in two months."
    )


def test_cohere_detokenize_no_key(cur_with_api_key):
    cur_with_api_key.execute("""
        select ai.cohere_detokenize
        ( 'command'
        , array[14485,38374,2630,2060,2252,5164,4905,21,2744,2628,1675,3094,23407,21]
        )
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert (
        actual
        == "Good programmers don't just write programs. They build a working vocabulary."
    )


def test_cohere_list_models_default_only(cur_with_api_key):
    cur_with_api_key.execute("""
        select count(*) > 0
        from ai.cohere_list_models(endpoint=>'generate', default_only=>true)
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual is True


def test_cohere_embed(cur, cohere_api_key):
    cur.execute(
        """
        select vector_dims
        (
            ai.cohere_embed
            ( 'embed-english-light-v3.0'
            , 'how much wood would a woodchuck chuck if a woodchuck could chuck wood?'
            , api_key=>%s
            , input_type=>'search_document'
            )
        )
    """,
        (cohere_api_key,),
    )
    actual = cur.fetchone()[0]
    assert actual == 384


def test_cohere_embed_api_key_name(cur_with_external_functions_executor_url):
    cur_with_external_functions_executor_url.execute(
        """
        select vector_dims
        (
            ai.cohere_embed
            ( 'embed-english-light-v3.0'
            , 'how much wood would a woodchuck chuck if a woodchuck could chuck wood?'
            , api_key_name=> 'COHERE_API_KEY_REAL'
            , input_type=>'search_document'
            )
        )
    """
    )
    actual = cur_with_external_functions_executor_url.fetchone()[0]
    assert actual == 384


def test_cohere_embed_no_key(cur_with_api_key):
    cur_with_api_key.execute("""
        select vector_dims
        (
            ai.cohere_embed
            ( 'embed-english-light-v3.0'
            , 'if a woodchuck could chuck wood, a woodchuck would chuck as much wood as he could'
            , input_type=>'search_document'
            , truncate_long_inputs=>'end'
            )
        )
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual == 384


def test_cohere_classify(cur_with_api_key):
    cur_with_api_key.execute("""
        with examples(example, label) as
        (
            values
              ('cat', 'animal')
            , ('dog', 'animal')
            , ('car', 'machine')
            , ('truck', 'machine')
            , ('apple', 'food')
            , ('broccoli', 'food')
        )
        select jsonb_object_agg(x.input, x.prediction)::text
        from jsonb_to_recordset
        ((
            select ai.cohere_classify
            ( 'embed-english-light-v3.0'
            , array['bird', 'airplane', 'corn']
            , examples=>(select jsonb_agg(jsonb_build_object('text', examples.example, 'label', examples.label)) from examples)
            )->'classifications'
        )) x(input text, prediction text)
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual == """{"bird": "animal", "corn": "food", "airplane": "machine"}"""


def test_cohere_classify_simple(cur_with_api_key):
    cur_with_api_key.execute("""
        with examples(example, label) as
        (
            values
              ('cat', 'animal')
            , ('dog', 'animal')
            , ('car', 'machine')
            , ('truck', 'machine')
            , ('apple', 'food')
            , ('broccoli', 'food')
        )
        select jsonb_object_agg(x.input, x.prediction)::text
        from ai.cohere_classify_simple
        ( 'embed-english-light-v3.0'
        , array['bird', 'airplane', 'corn']
        , examples=>(select jsonb_agg(jsonb_build_object('text', examples.example, 'label', examples.label)) from examples)
        ) x
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual == """{"bird": "animal", "corn": "food", "airplane": "machine"}"""


def test_cohere_rerank(cur_with_api_key):
    cur_with_api_key.execute("""
        with x as
        (
          select ai.cohere_rerank
          ( 'rerank-english-v3.0'
          , 'How long does it take for two programmers to work on something?'
          , jsonb_build_array
            ( $$Good programmers don't just write programs. They build a working vocabulary.$$
            , 'One of the best programming skills you can have is knowing when to walk away for awhile.'
            , 'What one programmer can do in one month, two programmers can do in two months.'
            , 'how much wood would a woodchuck chuck if a woodchuck could chuck wood?'
            )
          , return_documents=>true
          ) as actual
        )
        select y."index" as actual
        from x
        cross join lateral jsonb_to_recordset(x.actual->'results') y("index" int, "document" jsonb, relevance_score float8)
        order by y.relevance_score desc
        limit 1
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual == 2


def test_cohere_rerank_advanced(cur_with_api_key):
    cur_with_api_key.execute("""
        with docs(id, quote, author) as
        (
            values
              (1, $$Good programmers don't just write programs. They build a working vocabulary.$$, 'Guy Steele')
            , (2, 'One of the best programming skills you can have is knowing when to walk away for awhile.', 'Oscar Godson')
            , (3, 'What one programmer can do in one month, two programmers can do in two months.', 'Frederick P. Brooks')
            , (4, 'how much wood would a woodchuck chuck if a woodchuck could chuck wood?', 'some joker')
        )
        , x as
        (
            select ai.cohere_rerank
            ( 'rerank-english-v3.0'
            , 'How long does it take for two programmers to work on something?'
            , (select jsonb_agg(x) from docs x)
            , rank_fields=>array['quote']
            , return_documents=>true
            ) as actual
        )
        select y."document"->>'author' as actual
        from x
        cross join lateral jsonb_to_recordset(x.actual->'results') y("index" int, "document" jsonb, relevance_score float8)
        order by y.relevance_score desc
        limit 1
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual == "Frederick P. Brooks"


def test_cohere_rerank_simple(cur_with_api_key):
    cur_with_api_key.execute("""
        select x."index" as actual
        from ai.cohere_rerank_simple
        ( 'rerank-english-v3.0'
        , 'How long does it take for two programmers to work on something?'
        , jsonb_build_array
          ( $$Good programmers don't just write programs. They build a working vocabulary.$$
          , 'One of the best programming skills you can have is knowing when to walk away for awhile.'
          , 'What one programmer can do in one month, two programmers can do in two months.'
          , 'how much wood would a woodchuck chuck if a woodchuck could chuck wood?'
          )
        ) x
        order by relevance_score asc
        limit 1
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual == 3


def test_cohere_chat_complete(cur_with_api_key):
    cur_with_api_key.execute("""
        select ai.cohere_chat_complete
        ( 'command-r-plus'
        , 'How much wood would a woodchuck chuck if a woodchuck could chuck wood?'
        , seed=>42
        )->>'text' is not null
    """)
    actual = cur_with_api_key.fetchone()[0]
    assert actual is True
