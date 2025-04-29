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
    select json_strip_nulls(json_build_object
    ( 'implementation', 'table'
    , 'config_type', 'destination'
    , 'destination', destination
    , 'target_schema', target_schema
    , 'target_table', target_table
    , 'view_schema', view_schema
    , 'view_name', view_name
    ))
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
    select json_strip_nulls(json_build_object
    ( 'implementation', 'column'
    , 'config_type', 'destination'
    , 'embedding_column', embedding_column
    ))
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
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;


-------------------------------------------------------------------------------
-- evaluate_destination
create or replace function ai._evaluate_destination
( destination pg_catalog.jsonb,
source_schema pg_catalog.name,
source_table pg_catalog.name
) returns jsonb
as $func$
declare
    target_schema pg_catalog.name;
    target_table pg_catalog.name;
    view_schema pg_catalog.name;
    view_name pg_catalog.name;
begin
    if destination operator(pg_catalog.->>) 'implementation' = 'table' then
        target_schema = coalesce(destination operator(pg_catalog.->>) 'target_schema', source_schema);
        target_table = case
            when destination operator(pg_catalog.->>) 'target_table' is not null then destination operator(pg_catalog.->>) 'target_table'
            when destination operator(pg_catalog.->>) 'destination' is not null then pg_catalog.concat(destination operator(pg_catalog.->>) 'destination', '_store')
            else pg_catalog.concat(source_table, '_embedding_store')
        end;
        view_schema = coalesce(view_schema, source_schema);
        view_name = case
            when destination operator(pg_catalog.->>) 'view_name' is not null then destination operator(pg_catalog.->>) 'view_name'
            when destination operator(pg_catalog.->>) 'destination' is not null then destination operator(pg_catalog.->>) 'destination'
            else pg_catalog.concat(source_table, '_embedding')
        end;
        return json_build_object
        ( 'implementation', 'table'
        , 'config_type', 'destination'
        , 'target_schema', target_schema
        , 'target_table', target_table
        , 'view_schema', view_schema
        , 'view_name', view_name
        );
    elseif destination operator(pg_catalog.->>) 'implementation' = 'column' then
        return json_build_object
        ( 'implementation', 'column'
        , 'config_type', 'destination'
        , 'embedding_column', destination operator(pg_catalog.->>) 'embedding_column'
        );
    else
        raise exception 'invalid implementation for destination config';
    end if;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

create or replace function ai._validate_destination_can_create_objects(destination pg_catalog.jsonb) returns void
as $func$
declare
    _config_type pg_catalog.text;
begin
    if destination operator(pg_catalog.->>) 'implementation' = 'table' then
         -- make sure view name is available
        if pg_catalog.to_regclass(pg_catalog.format('%I.%I', destination operator(pg_catalog.->>) 'view_schema', destination operator(pg_catalog.->>) 'view_name')) is not null then
            raise exception 'an object named %.% already exists. specify an alternate destination or view_name explicitly', destination operator(pg_catalog.->>) 'view_schema', destination operator(pg_catalog.->>) 'view_name'
            using errcode = 'duplicate_object';
        end if;
    
        -- make sure target table name is available
        if pg_catalog.to_regclass(pg_catalog.format('%I.%I', destination operator(pg_catalog.->>) 'target_schema', destination operator(pg_catalog.->>) 'target_table')) is not null then
            raise exception 'an object named %.% already exists. specify an alternate destination or target_table explicitly', destination operator(pg_catalog.->>) 'target_schema', destination operator(pg_catalog.->>) 'target_table'
            using errcode = 'duplicate_object';
        end if;
    end if;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;