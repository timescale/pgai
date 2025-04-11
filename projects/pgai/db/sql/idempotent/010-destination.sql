-------------------------------------------------------------------------------
-- destination_table
create or replace function ai.destination_table
(
    destination pg_catalog.name default null
    , target_schema pg_catalog.name default null
    , target_table pg_catalog.name default null
    , view_schema pg_catalog.name default null
    , view_name pg_catalog.name default null
) returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'implementation': 'table'
    , 'config_type': 'destination'
    , 'destination': destination
    , 'target_schema': target_schema
    , 'target_table': target_table
    , 'view_schema': view_schema
    , 'view_name': view_name
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- destination_column
create or replace function ai.destination_column
(
    embedding_column pg_catalog.name
) returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'implementation': 'column'
    , 'config_type': 'destination'
    , 'embedding_column': embedding_column
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- validate_destination
create or replace function ai._validate_destination
( destination pg_catalog.jsonb
, chunking pg_catalog.jsonb ) returns void
as $func$
declare
    _config_type pg_catalog.text;
begin
    if pg_catalog.jsonb_typeof(destination) operator(pg_catalog.!=) 'object' then
        raise exception 'destination config is not a jsonb object';
    end if;

    _config_type = destination operator(pg_catalog.->>) 'config_type';
    if _config_type is null or _config_type operator(pg_catalog.!=) 'destination' then
        raise exception 'invalid config_type for destination config';
    end if;

    if destination->>'implementation' = 'column' then
        if chunking->>'implementation' != 'none' then
            raise exception 'chunking must be none for column destination';
        end if;
    end if;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;
