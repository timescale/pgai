--FEATURE-FLAG: text_to_sql

-------------------------------------------------------------------------------
-- text_to_sql_ollama
create or replace function ai.text_to_sql_ollama
( model pg_catalog.text
, host pg_catalog.text default null
, keep_alive pg_catalog.text default null
, chat_options pg_catalog.jsonb default null
) returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'provider': 'ollama'
    , 'model': model
    , 'host': host
    , 'keep_alive': keep_alive
    , 'chat_options': chat_options
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _text_to_sql_ollama
create function ai._text_to_sql_ollama
( question text
, catalog_name text default 'default'
, config jsonb default null -- TODO: use this for LLM configuration
) returns jsonb
as $func$
declare
begin
    raise exception 'not implemented yet';
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;