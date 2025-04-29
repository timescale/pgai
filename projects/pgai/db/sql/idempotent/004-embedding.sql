
-------------------------------------------------------------------------------
-- embedding_openai
create or replace function ai.embedding_openai
( model pg_catalog.text
, dimensions pg_catalog.int4
, chat_user pg_catalog.text default null
, api_key_name pg_catalog.text default 'OPENAI_API_KEY'
, base_url text default null
) returns pg_catalog.jsonb
as $func$
    select json_strip_nulls(json_build_object
    ( 'implementation', 'openai'
    , 'config_type', 'embedding'
    , 'model', model
    , 'dimensions', dimensions
    , 'user', chat_user
    , 'api_key_name', api_key_name
    , 'base_url', base_url
    ))
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- embedding_ollama
create or replace function ai.embedding_ollama
( model pg_catalog.text
, dimensions pg_catalog.int4
, base_url pg_catalog.text default null
, options pg_catalog.jsonb default null
, keep_alive pg_catalog.text default null
) returns pg_catalog.jsonb
as $func$
    select json_strip_nulls(json_build_object
    ( 'implementation', 'ollama'
    , 'config_type', 'embedding'
    , 'model', model
    , 'dimensions', dimensions
    , 'base_url', base_url
    , 'options', options
    , 'keep_alive', keep_alive
    ))
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- embedding_voyageai
create or replace function ai.embedding_voyageai
( model pg_catalog.text
, dimensions pg_catalog.int4
, input_type pg_catalog.text default 'document'
, api_key_name pg_catalog.text default 'VOYAGE_API_KEY'
) returns pg_catalog.jsonb
as $func$
begin
    if input_type is not null and input_type not in ('query', 'document') then
        -- Note: purposefully not using an enum here because types make life complicated
        raise exception 'invalid input_type for voyage ai "%"', input_type;
    end if;

    return json_strip_nulls(json_build_object
    ( 'implementation', 'voyageai'
    , 'config_type', 'embedding'
    , 'model', model
    , 'dimensions', dimensions
    , 'input_type', input_type
    , 'api_key_name', api_key_name
    ));
end
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- embedding_litellm
create or replace function ai.embedding_litellm
( model pg_catalog.text
, dimensions pg_catalog.int4
, api_key_name pg_catalog.text default null
, extra_options pg_catalog.jsonb default null
) returns pg_catalog.jsonb
as $func$
begin
    return json_strip_nulls(json_build_object
    ( 'implementation', 'litellm'
    , 'config_type', 'embedding'
    , 'model', model
    , 'dimensions', dimensions
    , 'api_key_name', api_key_name
    , 'extra_options', extra_options
    ));
end
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_embedding
create or replace function ai._validate_embedding(config pg_catalog.jsonb) returns void
as $func$
declare
    _config_type pg_catalog.text;
    _implementation pg_catalog.text;
begin
    if pg_catalog.jsonb_typeof(config) operator(pg_catalog.!=) 'object' then
        raise exception 'embedding config is not a jsonb object';
    end if;

    _config_type = config operator(pg_catalog.->>) 'config_type';
    if _config_type is null or _config_type operator(pg_catalog.!=) 'embedding' then
        raise exception 'invalid config_type for embedding config';
    end if;
    _implementation = config operator(pg_catalog.->>) 'implementation';
    case _implementation
        when 'openai' then
            -- ok
        when 'ollama' then
            -- ok
        when 'voyageai' then
            -- ok
        when 'litellm' then
            -- ok
        else
            if _implementation is null then
                raise exception 'embedding implementation not specified';
            else
                raise exception 'invalid embedding implementation: "%"', _implementation;
            end if;
    end case;
end
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;
