
-------------------------------------------------------------------------------
-- embedding_openai
create or replace function ai.embedding_openai
( model text
, dimensions int
, chat_user text default null
, api_key_name text default 'OPENAI_API_KEY'
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'openai'
    , 'config_type': 'embedding'
    , 'model': model
    , 'dimensions': dimensions
    , 'user': chat_user
    , 'api_key_name': api_key_name
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;
