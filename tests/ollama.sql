-------------------------------------------------------------------------------
-- get our ollama host
-- grab our ollama host from the environment as a psql variable
\getenv ollama_host OLLAMA_HOST
\if :{?ollama_host}
\else
\warn Ollama tests are enabled but OLLAMA_HOST is not set!
do $$
begin
raise exception 'Ollama tests are enabled but OLLAMA_HOST is not set!';
end;
$$;
\q
\endif

-- set our session local GUC
select set_config('ai.ollama_host', $1, false) is not null as set_ollama_host
\bind :ollama_host
\g

-------------------------------------------------------------------------------
-- register our tests
insert into tests (test)
values
  ('ollama_list_models')
, ('ollama_list_models-no-host')
, ('ollama_embed')
, ('ollama_embed-no-host')
, ('ollama_generate')
, ('ollama_generate-no-host')
, ('ollama_generate-image')
, ('ollama_chat_complete')
, ('ollama_chat_complete-no-host')
, ('ollama_chat_complete-image')
, ('ollama_ps')
, ('ollama_ps-no-host')
-- add entries for new tests here!
;

-------------------------------------------------------------------------------
-- ollama_list_models
\set testname ollama_list_models
\set expected t
\echo :testname

select count(*) > 0 as actual
from ai.ollama_list_models(_host=>$1)
\bind :ollama_host
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- ollama_list_models-no-host
\set testname ollama_list_models-no-host
\set expected t
\echo :testname

select count(*) > 0 as actual
from ai.ollama_list_models()
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- ollama_embed
\set testname ollama_embed
\set expected 4096
\echo :testname

select vector_dims
(
    ai.ollama_embed
    ( 'llama3'
    , 'the purple elephant sits on a red mushroom'
    , _host=>$1
    )
) as actual
\bind :ollama_host
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- ollama_embed-no-host
\set testname ollama_embed-no-host
\set expected 4096
\echo :testname

select vector_dims
(
    ai.ollama_embed
    ( 'llama3'
    , 'the purple elephant sits on a red mushroom'
    )
) as actual
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- ollama_generate
\set testname ollama_generate
\set expected t
\echo :testname

select ai.ollama_generate
( 'llama3'
, 'what is the typical weather like in Alabama in June'
, _system=>'you are a helpful assistant'
, _host=>$1
, _options=> jsonb_build_object
  ( 'seed', 42
  , 'temperature', 0.6
  )
) as actual
\bind :ollama_host
\gset

\if :{?actual}
select (:'actual'::jsonb)->>'response' is not null and ((:'actual'::jsonb)->>'done')::boolean as actual
\gset
\endif

\ir eval.sql

-------------------------------------------------------------------------------
-- ollama_generate-no-host
\set testname ollama_generate-no-host
\set expected t
\echo :testname

select ai.ollama_generate
( 'llama3'
, 'what is the typical weather like in Alabama in June'
, _system=>'you are a helpful assistant'
, _options=> jsonb_build_object
  ( 'seed', 42
  , 'temperature', 0.6
  )
) as actual
\gset

\if :{?actual}
select (:'actual'::jsonb)->>'response' is not null and ((:'actual'::jsonb)->>'done')::boolean as actual
\gset
\endif

\ir eval.sql

-------------------------------------------------------------------------------
-- ollama_generate-image
\set testname ollama_generate-image
\set expected t
\echo :testname

select ai.ollama_generate
( 'llava:7b'
, 'Please describe this image.'
, _images=> array[pg_read_binary_file('/pgai/tests/postgresql-vs-pinecone.jpg')]
, _system=>'you are a helpful assistant'
, _options=> jsonb_build_object
  ( 'seed', 42
  , 'temperature', 0.9
  )
)->>'response' as actual
\gset

\if :{?actual}
select :'actual' ilike '%boxing gloves%' as actual
\gset
\endif

\ir eval.sql

-------------------------------------------------------------------------------
-- ollama_chat_complete
\set testname ollama_chat_complete
\set expected t
\echo :testname

select ai.ollama_chat_complete
( 'llama3'
, jsonb_build_array
  ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
  , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
  )
, _host=>$1
, _options=> jsonb_build_object
  ( 'seed', 42
  , 'temperature', 0.6
  )
) as actual
\bind :ollama_host
\gset

\if :{?actual}
select (:'actual'::jsonb)->'message'->>'content' is not null and ((:'actual'::jsonb)->>'done')::boolean as actual
\gset
\endif

\ir eval.sql

-------------------------------------------------------------------------------
-- ollama_chat_complete-no-host
\set testname ollama_chat_complete-no-host
\set expected t
\echo :testname

select ai.ollama_chat_complete
( 'llama3'
, jsonb_build_array
  ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
  , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
  )
, _options=> jsonb_build_object
  ( 'seed', 42
  , 'temperature', 0.6
  )
) as actual
\gset

\if :{?actual}
select (:'actual'::jsonb)->'message'->>'content' is not null and ((:'actual'::jsonb)->>'done')::boolean as actual
\gset
\endif

\ir eval.sql

-------------------------------------------------------------------------------
-- ollama_chat_complete-image
\set testname ollama_chat_complete-image
\set expected t
\echo :testname

select ai.ollama_chat_complete
( 'llava:7b'
, jsonb_build_array
  ( jsonb_build_object
    ( 'role', 'user'
    , 'content', 'describe this image'
    , 'images', jsonb_build_array(encode(pg_read_binary_file('/pgai/tests/postgresql-vs-pinecone.jpg'), 'base64'))
    )
  )
, _options=> jsonb_build_object
  ( 'seed', 42
  , 'temperature', 0.9
  )
)->'message'->>'content' as actual
\gset

\if :{?actual}
select starts_with(:'actual'::text, ' This is a digitally manipulated image') as actual
\gset
\endif

\ir eval.sql

-------------------------------------------------------------------------------
-- ollama_ps
\set testname ollama_ps
\set expected 1
\echo :testname

select count(*) filter (where "name" = 'llava:7b') as actual
from ai.ollama_ps(_host=>$1)
\bind :ollama_host
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- ollama_ps-no-host
\set testname ollama_ps-no-host
\set expected 1
\echo :testname

select count(*) filter (where "name" = 'llava:7b') as actual
from ai.ollama_ps()
\gset

\ir eval.sql
