-------------------------------------------------------------------------------
-- destination_custom
create or replace function ai.destination_default
(
    destination pg_catalog.name default null
    , target_schema pg_catalog.name default null
    , target_table pg_catalog.name default null
    , view_schema pg_catalog.name default null
    , view_name pg_catalog.name default null
) returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'implementation': 'default'
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
-- destination_source
create or replace function ai.destination_source
(
    embedding_column pg_catalog.name
) returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'implementation': 'source'
    , 'config_type': 'destination'
    , 'embedding_column': embedding_column
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;
