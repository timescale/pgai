
-------------------------------------------------------------------------------
-- formatting_python_template
create or replace function ai.formatting_python_template
( template text default '$chunk'
, columns name[] default null
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'python_template'
    , 'config_type': 'formatting'
    , 'columns': columns
    , 'template': template
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_formatting_python_template
create or replace function ai._validate_formatting_python_template
( config jsonb
, source_schema name
, source_table name
) returns jsonb
as $func$
declare
    _template text;
    _found bool;
    _columns name[];
    _msg text;
begin
    select config operator(pg_catalog.->>) 'template'
    into strict _template
    ;
    if not pg_catalog.like(_template, '%$chunk%') then
        raise exception 'template must contain $chunk placeholder';
    end if;

    -- list the columns on the source table
    select array_agg(a.attname) into strict _columns
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace = n.oid)
    inner join pg_catalog.pg_attribute a on (k.oid = a.attrelid)
    where n.nspname operator(pg_catalog.=) source_schema
    and k.relname operator(pg_catalog.=) source_table
    and a.attnum operator(pg_catalog.>) 0
    ;
    if not found or pg_catalog.array_length(_columns, 1) operator(pg_catalog.=) 0 then
        raise exception 'source table not found';
    end if;

    -- make sure no source column is named "chunk"
    select 'chunk' = any(_columns) into strict _found;
    if _found then
        raise exception 'formatting_python_template may not be used when source table has a column named "chunk"';
    end if;

    -- if the user didn't specify a list of columns, use ALL columns
    -- otherwise, check that the columns specified actually exist
    if config operator(pg_catalog.->) 'columns' is null then
        select pg_catalog.jsonb_set
        ( config
        , array['columns']
        , pg_catalog.to_jsonb(_columns)
        , create_if_missing=>true
        ) into strict config
        ;
    else
        -- ensure the the columns listed in the config exist in the table
        -- find the columns in the config that do NOT exist in the table. hoping for zero results
        select pg_catalog.array_agg(x.x) into _columns
        from
        (
            select x
            from pg_catalog.jsonb_array_elements_text(config operator(pg_catalog.->) 'columns') x
            except
            select a.attname
            from pg_catalog.pg_class k
            inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
            inner join pg_catalog.pg_attribute a on (k.oid operator(pg_catalog.=) a.attrelid)
            where n.nspname operator(pg_catalog.=) source_schema
            and k.relname operator(pg_catalog.=) source_table
            and a.attnum operator(pg_catalog.>) 0
        ) x
        ;
        if found and _columns is not null and pg_catalog.array_length(_columns, 1) operator(pg_catalog.>) 0 then
            select pg_catalog.string_agg(x, ', ')
            into strict _msg
            from pg_catalog.unnest(_columns) x
            ;
            raise exception 'columns in config do not exist in the table: %', _msg;
        end if;
    end if;

    return config;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_formatting
create or replace function ai._validate_formatting
( config jsonb
, source_schema name
, source_table name
) returns jsonb
as $func$
declare
    _config_type text;
begin
    _config_type = config operator ( pg_catalog.->> ) 'config_type';
    if _config_type is null or _config_type != 'formatting' then
        raise exception 'invalid config_type for formatting config';
    end if;
    case config operator(pg_catalog.->>) 'implementation'
        when 'python_template' then
            config = ai._validate_formatting_python_template
            ( config
            , source_schema
            , source_table
            );
        else
            raise exception 'unrecognized formatting implementation';
    end case;
    return config;
end
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;
