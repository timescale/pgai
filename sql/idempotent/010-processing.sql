
-------------------------------------------------------------------------------
-- processing_none
create or replace function ai.processing_none() returns jsonb
as $func$
    select jsonb_build_object
    ( 'implementation', 'none'
    , 'config_type', 'processing'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- processing_cloud_functions
create or replace function ai.processing_cloud_functions
( batch_size int default 50
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'cloud_functions'
    , 'config_type': 'processing'
    , 'batch_size': batch_size
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_processing
create or replace function ai._validate_processing(config jsonb) returns void
as $func$
declare
    _config_type text;
    _implementation text;
    _val jsonb;
begin
    if pg_catalog.jsonb_typeof(config) != 'object' then
        raise exception 'processing config is not a jsonb object';
    end if;

    _config_type = config operator ( pg_catalog.->> ) 'config_type';
    if _config_type is null or _config_type != 'processing' then
        raise exception 'invalid config_type for processing config';
    end if;
    _implementation = config operator(pg_catalog.->>) 'implementation';
    case _implementation
        when 'none' then
            -- ok
        when 'cloud_functions' then
            _val = pg_catalog.jsonb_extract_path(config, 'batch_size');
            if pg_catalog.jsonb_typeof(_val) operator(pg_catalog.!=) 'number' then
                raise exception 'batch_size must be a number';
            end if;
            if cast(_val as int) > 2048 then
                raise exception 'batch_size must be less than or equal to 2048';
            end if;
        else
            if _implementation is null then
                raise exception 'processing implementation not specified';
            else
                raise exception 'unrecognized processing implementation: "%"', _implementation;
            end if;
    end case;
end
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;
