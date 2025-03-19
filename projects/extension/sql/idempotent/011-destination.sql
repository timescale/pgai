-------------------------------------------------------------------------------
-- destination_default
create or replace function ai.destination_default
( ) returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'implementation': 'default'
    , 'config_type': 'destination'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- destination_custom
create or replace function ai.destination_custom
(
    destination pg_catalog.name default null
    , target_schema pg_catalog.name default null
    , target_table pg_catalog.name default null
    , view_schema pg_catalog.name default null
    , view_name pg_catalog.name default null
) returns pg_catalog.jsonb
as $func$
    target_schema = coalesce(target_schema, _source_schema);
    target_table = case
        when target_table is not null then target_table
        when destination is not null then pg_catalog.concat(destination, '_store')
        else pg_catalog.concat(_source_table, '_embedding_store')
    end;
    view_schema = coalesce(view_schema, _source_schema);
    view_name = case
        when view_name is not null then view_name
        when destination is not null then destination
        else pg_catalog.concat(_source_table, '_embedding')
    end;
    -- make sure view name is available
    if pg_catalog.to_regclass(pg_catalog.format('%I.%I', view_schema, view_name)) is not null then
        raise exception 'an object named %.% already exists. specify an alternate destination explicitly', view_schema, view_name;
    end if;

    -- make sure target table name is available
    if pg_catalog.to_regclass(pg_catalog.format('%I.%I', target_schema, target_table)) is not null then
        raise exception 'an object named %.% already exists. specify an alternate destination or target_table explicitly', target_schema, target_table;
    end if;
    select json_object
    ( 'implementation': 'custom'
    , 'config_type': 'destination'
    , 'target_schema': target_schema
    , 'target_table': target_table
    , 'view_schema': view_schema
    , 'view_name': view_name
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
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;


-------------------------------------------------------------------------------
-- _validate_destination
create or replace function ai._validate_destination
(
    destination jsonb
) returns void
as $func$
