-------------------------------------------------------------------------------
-- get our cohere api key
\getenv cohere_api_key COHERE_API_KEY
\if :{?cohere_api_key}
\else
\warn Cohere tests are enabled but COHERE_API_KEY is not set!
do $$
begin
raise exception 'Cohere tests are enabled but COHERE_API_KEY is not set!';
end;
$$;
\q
\endif

-- set our session local GUC
select set_config('ai.cohere_api_key', $1, false) is not null as set_cohere_api_key
\bind :cohere_api_key
\g

-------------------------------------------------------------------------------
-- register our tests
insert into tests (test)
values
  ('cohere_list_models')
, ('cohere_list_models-no-key')
, ('cohere_list_models-endpoint')
, ('cohere_list_models-default-only')
, ('cohere_tokenize')
, ('cohere_tokenize-no-key')
, ('cohere_detokenize')
, ('cohere_detokenize-no-key')
, ('cohere_embed')
, ('cohere_embed-no-key')
, ('cohere_classify')
, ('cohere_classify_simple')
, ('cohere_rerank')
, ('cohere_rerank_simple')
, ('cohere_chat_complete')
-- add entries for new tests here!
;

-------------------------------------------------------------------------------
-- cohere_list_models
\set testname cohere_list_models
\set expected t
\echo :testname

select count(*) > 0 as actual
from ai.cohere_list_models(_api_key=>$1)
\bind :cohere_api_key
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- cohere_list_models-no-key
\set testname cohere_list_models-no-key
\set expected t
\echo :testname

select count(*) > 0 as actual
from ai.cohere_list_models()
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- cohere_list_models-endpoint
\set testname cohere_list_models-endpoint
\set expected t
\echo :testname

select count(*) > 0 as actual
from ai.cohere_list_models(_endpoint=>'embed')
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- cohere_tokenize
\set testname cohere_tokenize
\set expected 17
\echo :testname

select array_length
(
    ai.cohere_tokenize
    ( 'command'
    , 'What one programmer can do in one month, two programmers can do in two months.'
    , _api_key=>$1
    )
, 1
) as actual
\bind :cohere_api_key
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- cohere_tokenize-no-key
\set testname cohere_tokenize-no-key
\set expected {5256,1707,1682,2383,9461,4696,1739,1863,1871,1740,9397,2112,1705,4066,3465,1742,38700,21}
\echo :testname

select ai.cohere_tokenize
( 'command'
, 'One of the best programming skills you can have is knowing when to walk away for awhile.'
) as actual
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- cohere_detokenize
\set testname cohere_detokenize
select 'What one programmer can do in one month, two programmers can do in two months.' as expected \gset
\echo :testname

select ai.cohere_detokenize
( 'command'
, array[5171,2011,36613,1863,1978,1703,2011,2812,19,2253,38374,1863,1978,1703,2253,3784,21]
, _api_key=>$1
) as actual
\bind :cohere_api_key
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- cohere_detokenize-no-key
\set testname cohere_detokenize-no-key
select $$Good programmers don't just write programs. They build a working vocabulary.$$ as expected \gset
\echo :testname

select ai.cohere_detokenize
( 'command'
, array[14485,38374,2630,2060,2252,5164,4905,21,2744,2628,1675,3094,23407,21]
) as actual
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- cohere_list_models-default-only
\set testname cohere_list_models-default-only
\set expected t
\echo :testname

select count(*) > 0 as actual
from ai.cohere_list_models(_endpoint=>'generate', _default_only=>true)
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- cohere_embed
\set testname cohere_embed
\set expected 384
\echo :testname

select vector_dims
(
    ai.cohere_embed
    ( 'embed-english-light-v3.0'
    , 'how much wood would a woodchuck chuck if a woodchuck could chuck wood?'
    , _api_key=>$1
    , _input_type=>'search_document'
    )
) as actual
\bind :cohere_api_key
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- cohere_embed-no-key
\set testname cohere_embed-no-key
\set expected 384
\echo :testname

select vector_dims
(
    ai.cohere_embed
    ( 'embed-english-light-v3.0'
    , 'if a woodchuck could chuck wood, a woodchuck would chuck as much wood as he could'
    , _input_type=>'search_document'
    , _truncate=>'end'
    )
) as actual
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- cohere_classify
\set testname cohere_classify
select '{"bird": "animal", "corn": "food", "airplane": "machine"}'::jsonb::text as expected \gset
\echo :testname

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
select jsonb_object_agg(x.input, x.prediction) as actual
from jsonb_to_recordset
((
    select ai.cohere_classify
    ( 'embed-english-light-v3.0'
    , array['bird', 'airplane', 'corn']
    , _examples=>(select jsonb_agg(jsonb_build_object('text', examples.example, 'label', examples.label)) from examples)
    )->'classifications'
)) x(input text, prediction text)
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- cohere_classify_simple
\set testname cohere_classify_simple
select '{"bird": "animal", "corn": "food", "airplane": "machine"}'::jsonb::text as expected \gset
\echo :testname

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
select jsonb_object_agg(x.input, x.prediction) as actual
from ai.cohere_classify_simple
( 'embed-english-light-v3.0'
, array['bird', 'airplane', 'corn']
, _examples=>(select jsonb_agg(jsonb_build_object('text', examples.example, 'label', examples.label)) from examples)
) x
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- cohere_rerank
\set testname cohere_rerank
\set expected 2
\echo :testname

select ai.cohere_rerank
( 'rerank-english-v3.0'
, 'How long does it take for two programmers to work on something?'
, jsonb_build_array
  ( $$Good programmers don't just write programs. They build a working vocabulary.$$
  , 'One of the best programming skills you can have is knowing when to walk away for awhile.'
  , 'What one programmer can do in one month, two programmers can do in two months.'
  , 'how much wood would a woodchuck chuck if a woodchuck could chuck wood?'
  )
, _return_documents=>true
) as actual
\gset

\if :{?actual}
select x."index" as actual
from jsonb_to_recordset((:'actual'::jsonb)->'results') x("index" int, "document" jsonb, relevance_score float8)
order by relevance_score desc
limit 1
\gset
\endif

\ir eval.sql

-------------------------------------------------------------------------------
-- cohere_rerank_simple
\set testname cohere_rerank_simple
\set expected 3
\echo :testname

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
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- cohere_chat_complete
\set testname cohere_chat_complete
\set expected t
\echo :testname

select ai.cohere_chat_complete
( 'command-r-plus'
, 'How much wood would a woodchuck chuck if a woodchuck could chuck wood?'
, _seed=>42
)->>'text' is not null as actual
\gset

\ir eval.sql

-------------------------------------------------------------------------------
