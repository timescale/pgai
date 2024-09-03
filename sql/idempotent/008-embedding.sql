
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

-------------------------------------------------------------------------------
-- _validate_embedding
create or replace function ai._validate_embedding(config jsonb) returns void
as $func$
declare
    _config_type text;
    _implementation text;
begin
    _config_type = config operator ( pg_catalog.->> ) 'config_type';
    if _config_type is null or _config_type != 'embedding' then
        raise exception 'invalid config_type for embedding config';
    end if;
    _implementation = config operator(pg_catalog.->>) 'implementation';
    case _implementation
        when 'openai' then
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
