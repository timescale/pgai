-------------------------------------------------------------------------------
-- get our openai api key
-- grab our api key from the environment as a psql variable
\getenv openai_api_key OPENAI_API_KEY
\if :{?openai_api_key}
\else
\warn OpenAI tests are enabled but OPENAI_API_KEY is not set!
do $$
begin
raise exception 'OpenAI tests are enabled but OPENAI_API_KEY is not set!';
end;
$$;
\q
\endif

-- set our session local GUC
select set_config('ai.openai_api_key', $1, false) is not null as set_openai_api_key
\bind :openai_api_key
\g

-------------------------------------------------------------------------------
-- register our tests
insert into tests (test)
values
  ('openai_list_models')
, ('openai_list_models-no-key')
, ('openai_tokenize')
, ('openai_detokenize')
, ('openai_embed-1')
, ('openai_embed-1-no-key')
, ('openai_embed-2')
, ('openai_embed-2-no-key')
, ('openai_embed-3')
, ('openai_embed-3-no-key')
, ('openai_embed-4')
, ('openai_embed-4-no-key')
, ('openai_embed-5')
, ('openai_embed-5-no-key')
, ('openai_chat_complete')
, ('openai_chat_complete-no-key')
, ('openai_moderate')
, ('openai_moderate-no-key')
-- add entries for new tests here!
;

-------------------------------------------------------------------------------
-- openai_list_models
\set testname openai_list_models
\set expected t
\echo :testname

select count(*) > 0 as actual
from ai.openai_list_models(_api_key=>$1)
\bind :openai_api_key
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_list_models-no-key
\set testname openai_list_models-no-key
\set expected t
\echo :testname

select count(*) > 0 as actual
from ai.openai_list_models()
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_tokenize
\set testname openai_tokenize
select array[1820,25977,46840,23874,389,264,2579,58466]::text as expected \gset
\echo :testname

select ai.openai_tokenize('text-embedding-ada-002', 'the purple elephant sits on a red mushroom')::text as actual
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_detokenize
\set testname openai_detokenize
select 'the purple elephant sits on a red mushroom' as expected \gset
\echo :testname

select ai.openai_detokenize('text-embedding-ada-002', array[1820,25977,46840,23874,389,264,2579,58466]) as actual
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_embed-1
\set testname openai_embed-1
\set expected 1536
\echo :testname

select vector_dims
(
    ai.openai_embed
    ( 'text-embedding-ada-002'
    , 'the purple elephant sits on a red mushroom'
    , _api_key=>$1
    )
) as actual
\bind :openai_api_key
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_embed-1-no-key
\set testname openai_embed-1-no-key
\set expected 1536
\echo :testname

select vector_dims
(
    ai.openai_embed
    ( 'text-embedding-ada-002'
    , 'the purple elephant sits on a red mushroom'
    )
) as actual
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_embed-2
\set testname openai_embed-2
\set expected 768
\echo :testname

select vector_dims
(
    ai.openai_embed
    ( 'text-embedding-3-large'
    , 'the purple elephant sits on a red mushroom'
    , _api_key=>$1
    , _dimensions=>768
    )
) as actual
\bind :openai_api_key
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_embed-2-no-key
\set testname openai_embed-2-no-key
\set expected 768
\echo :testname

select vector_dims
(
    ai.openai_embed
    ( 'text-embedding-3-large'
    , 'the purple elephant sits on a red mushroom'
    , _dimensions=>768
    )
) as actual
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_embed-3
\set testname openai_embed-3
\set expected 3072
\echo :testname

select vector_dims
(
    ai.openai_embed
    ( 'text-embedding-3-large'
    , 'the purple elephant sits on a red mushroom'
    , _api_key=>$1
    , _user=>'bob'
    )
) as actual
\bind :openai_api_key
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_embed-3-no-key
\set testname openai_embed-3-no-key
\set expected 3072
\echo :testname

select vector_dims
(
    ai.openai_embed
    ( 'text-embedding-3-large'
    , 'the purple elephant sits on a red mushroom'
    , _user=>'bob'
    )
) as actual
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_embed-4
\set testname openai_embed-4
\set expected 6144
\echo :testname

select sum(vector_dims(embedding)) as actual
from ai.openai_embed
( 'text-embedding-3-large'
, array['the purple elephant sits on a red mushroom', 'timescale is postgres made powerful']
, _api_key=>$1
)
\bind :openai_api_key
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_embed-4-no-key
\set testname openai_embed-4-no-key
\set expected 6144
\echo :testname

select sum(vector_dims(embedding)) as actual
from ai.openai_embed
( 'text-embedding-3-large'
, array['the purple elephant sits on a red mushroom', 'timescale is postgres made powerful']
)
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_embed-5
\set testname openai_embed-5
\set expected 1536
\echo :testname

select vector_dims
(
    ai.openai_embed
    ( 'text-embedding-ada-002'
    , array[1820,25977,46840,23874,389,264,2579,58466]
    , _api_key=>$1
    )
) as actual
\bind :openai_api_key
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_embed-5-no-key
\set testname openai_embed-5-no-key
\set expected 1536
\echo :testname

select vector_dims
(
    ai.openai_embed
    ( 'text-embedding-ada-002'
    , array[1820,25977,46840,23874,389,264,2579,58466]
    )
) as actual
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_chat_complete
\set testname openai_chat_complete
\set expected t
\echo :testname

select ai.openai_chat_complete
( 'gpt-4o'
, jsonb_build_array
  ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
  , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
  )
, _api_key=>$1
) as actual
\bind :openai_api_key
\gset

\if :{?actual}
select jsonb_extract_path_text(:'actual'::jsonb, 'choices', '0', 'message', 'content') is not null as actual
\gset
\endif

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_chat_complete-no-key
\set testname openai_chat_complete-no-key
\set expected t
\echo :testname

select ai.openai_chat_complete
( 'gpt-4o'
, jsonb_build_array
  ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
  , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
  )
) as actual
\gset

\if :{?actual}
select jsonb_extract_path_text(:'actual'::jsonb, 'choices', '0', 'message', 'content') is not null as actual
\gset
\endif

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_moderate
\set testname openai_moderate
\set expected t
\echo :testname

select ai.openai_moderate
( 'text-moderation-stable'
, 'I want to kill them.'
, _api_key=>$1
) as actual
\bind :openai_api_key
\gset

\if :{?actual}
select jsonb_extract_path_text(:'actual'::jsonb, 'results', '0', 'flagged')::bool as actual
\gset
\endif

\ir eval.sql

-------------------------------------------------------------------------------
-- openai_moderate-no-key
\set testname openai_moderate-no-key
\set expected t
\echo :testname

select ai.openai_moderate
( 'text-moderation-stable'
, 'I want to kill them.'
) as actual
\gset

\if :{?actual}
select jsonb_extract_path_text(:'actual'::jsonb, 'results', '0', 'flagged')::bool as actual
\gset
\endif

\ir eval.sql

-------------------------------------------------------------------------------
