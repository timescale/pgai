
-------------------------------------------------------------------------------
-- formatting_python_template
create or replace function ai.formatting_python_template(template pg_catalog.text default '$chunk') returns pg_catalog.jsonb
as $func$
    select json_strip_nulls(json_build_object
    ( 'implementation', 'python_template'
    , 'config_type', 'formatting'
    , 'template', template
    ))
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_formatting_python_template
create or replace function ai._validate_formatting_python_template
( config pg_catalog.jsonb
, source_schema pg_catalog.name
, source_table pg_catalog.name
) returns void
as $func$
declare
    _template pg_catalog.text;
    _found pg_catalog.bool;
begin
    select config operator(pg_catalog.->>) 'template'
    into strict _template
    ;
    if not pg_catalog.like(_template, '%$chunk%') then
        raise exception 'template must contain $chunk placeholder';
    end if;

    -- check that no columns on the source table are named "chunk"
    select count(*) operator(pg_catalog.>) 0 into strict _found
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace = n.oid)
    inner join pg_catalog.pg_attribute a on (k.oid = a.attrelid)
    where n.nspname operator(pg_catalog.=) source_schema
    and k.relname operator(pg_catalog.=) source_table
    and a.attnum operator(pg_catalog.>) 0
    and a.attname operator(pg_catalog.=) 'chunk'
    ;
    if _found then
        raise exception 'formatting_python_template may not be used when source table has a column named "chunk"';
    end if;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_formatting
create or replace function ai._validate_formatting
( config pg_catalog.jsonb
, source_schema pg_catalog.name
, source_table pg_catalog.name
) returns void
as $func$
declare
    _config_type pg_catalog.text;
begin
    if pg_catalog.jsonb_typeof(config) != 'object' then
        raise exception 'formatting config is not a jsonb object';
    end if;

    _config_type = config operator ( pg_catalog.->> ) 'config_type';
    if _config_type is null or _config_type operator(pg_catalog.!=) 'formatting' then
        raise exception 'invalid config_type for formatting config';
    end if;
    case config operator(pg_catalog.->>) 'implementation'
        when 'python_template' then
            perform ai._validate_formatting_python_template
            ( config
            , source_schema
            , source_table
            );
        else
            raise exception 'unrecognized formatting implementation';
    end case;
end
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;
