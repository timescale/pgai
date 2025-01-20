--FEATURE-FLAG: text_to_sql

-------------------------------------------------------------------------------
-- text_to_sql_openai
create or replace function ai.text_to_sql_openai
( model pg_catalog.text
, api_key pg_catalog.text default null
, api_key_name pg_catalog.text default null
, base_url pg_catalog.text default null
, frequency_penalty pg_catalog.float8 default null
, logit_bias pg_catalog.jsonb default null
, logprobs pg_catalog.bool default null
, top_logprobs pg_catalog.int4 default null
, max_tokens pg_catalog.int4 default null
, n pg_catalog.int4 default null
, presence_penalty pg_catalog.float8 default null
, seed pg_catalog.int4 default null
, stop pg_catalog.text default null
, temperature pg_catalog.float8 default null
, top_p pg_catalog.float8 default null
, openai_user pg_catalog.text default null
) returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'provider': 'openai'
    , 'model': model
    , 'api_key': api_key
    , 'api_key_name': api_key_name
    , 'base_url': base_url
    , 'frequency_penalty': frequency_penalty
    , 'logit_bias': logit_bias
    , 'logprobs': logprobs
    , 'top_logprobs': top_logprobs
    , 'max_tokens': max_tokens
    , 'n': n
    , 'presence_penalty': presence_penalty
    , 'seed': seed
    , 'stop': stop
    , 'temperature': temperature
    , 'top_p': top_p
    , 'openai_user': openai_user
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _text_to_sql_openai
create function ai._text_to_sql_openai
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