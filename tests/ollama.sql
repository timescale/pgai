-------------------------------------------------------------------------------
-- get our ollama host
-- grab our ollama host from the environment as a psql variable
\getenv ollama_host OLLAMA_HOST
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
\echo ollama_list_models
select count(*) as actual
from ollama_list_models(_host=>$1)
\bind :ollama_host
\gset

update tests set
  expected = true
, actual = :actual > 0
where test = 'ollama_list_models'
;
\unset actual

-------------------------------------------------------------------------------
-- ollama_list_models-no-host
\echo ollama_list_models-no-host
select count(*) as actual
from ollama_list_models()
\gset

update tests set
  expected = true
, actual = :actual > 0
where test = 'ollama_list_models-no-host'
;
\unset actual

-------------------------------------------------------------------------------
-- ollama_embed
\echo ollama_embed
select vector_dims
(
    ollama_embed
    ( 'llama3'
    , 'the purple elephant sits on a red mushroom'
    , _host=>$1
    )
) as actual
\bind :ollama_host
\gset

update tests set
  expected = 4096
, actual = :'actual'
where test = 'ollama_embed'
;
\unset actual

-------------------------------------------------------------------------------
-- ollama_embed-no-host
\echo ollama_embed-no-host
select vector_dims
(
    ollama_embed
    ( 'llama3'
    , 'the purple elephant sits on a red mushroom'
    )
) as actual
\gset

update tests set
  expected = 4096
, actual = :'actual'
where test = 'ollama_embed-no-host'
;
\unset actual

-------------------------------------------------------------------------------
-- ollama_generate
\echo ollama_generate
select ollama_generate
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

select (:'actual'::jsonb)->>'response' is not null and ((:'actual'::jsonb)->>'done')::boolean as actual
\gset

update tests set
  expected = true::text
, actual = :'actual'::bool::text
where test = 'ollama_generate'
;
\unset actual

-------------------------------------------------------------------------------
-- ollama_generate-no-host
\echo ollama_generate-no-host
select ollama_generate
( 'llama3'
, 'what is the typical weather like in Alabama in June'
, _system=>'you are a helpful assistant'
, _options=> jsonb_build_object
  ( 'seed', 42
  , 'temperature', 0.6
  )
) as actual
\gset

select (:'actual'::jsonb)->>'response' is not null and ((:'actual'::jsonb)->>'done')::boolean as actual
\gset

update tests set
  expected = true::text
, actual = :'actual'::bool::text
where test = 'ollama_generate-no-host'
;
\unset actual

-------------------------------------------------------------------------------
-- ollama_generate-image
\echo ollama_generate-image
select ollama_generate
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

update tests set
  expected = 'an elephant with boxing gloves on, ready for a fight'::text
, actual = substring(:'actual' from 152 for 52)
where test = 'ollama_generate-image'
;
\unset actual

-------------------------------------------------------------------------------
-- ollama_chat_complete
\echo ollama_chat_complete
select ollama_chat_complete
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

select (:'actual'::jsonb)->'message'->>'content' is not null and ((:'actual'::jsonb)->>'done')::boolean as actual
\gset

update tests set
  expected = true::text
, actual = :'actual'::bool::text
where test = 'ollama_chat_complete'
;
\unset actual

-------------------------------------------------------------------------------
-- ollama_chat_complete-no-host
\echo ollama_chat_complete-no-host
select ollama_chat_complete
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

select (:'actual'::jsonb)->'message'->>'content' is not null and ((:'actual'::jsonb)->>'done')::boolean as actual
\gset

update tests set
  expected = true::text
, actual = :'actual'::bool::text
where test = 'ollama_chat_complete-no-host'
;
\unset actual

-------------------------------------------------------------------------------
-- ollama_chat_complete-image
\echo ollama_chat_complete-image
select ollama_chat_complete
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

update tests set
  expected = true::text
, actual = starts_with(:'actual'::text, ' This is a digitally manipulated image')
where test = 'ollama_chat_complete-image'
;
\unset actual

-------------------------------------------------------------------------------
-- ollama_ps
\echo ollama_ps
select count(*) filter (where "name" = 'llava:7b') as actual
from ollama_ps(_host=>$1)
\bind :ollama_host
\gset

update tests set
  expected = '1'
, actual = :'actual'::text
where test = 'ollama_ps'
;
\unset actual

-------------------------------------------------------------------------------
-- ollama_ps-no-host
\echo ollama_ps-no-host
select count(*) filter (where "name" = 'llava:7b') as actual
from ollama_ps()
\gset

update tests set
  expected = '1'
, actual = :'actual'::text
where test = 'ollama_ps-no-host'
;
\unset actual
