-------------------------------------------------------------------------------
-- loading_row
create or replace function ai.loading_row
( column_name pg_catalog.text)
returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'implementation': 'row'
    , 'config_type': 'loading'
    , 'column_name': column_name
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- loading_document
create or replace function ai.loading_document
( column_name pg_catalog.text)
returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'implementation': 'document'
    , 'config_type': 'loading'
    , 'column_name': column_name
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_loading
create or replace function ai._validate_loading
( config pg_catalog.jsonb
, source_schema pg_catalog.name
, source_table pg_catalog.name
) returns void
as $func$
declare
    _config_type pg_catalog.text;
    _implementation pg_catalog.text;
    _column_name pg_catalog.text;
    _found pg_catalog.bool;
begin
    if pg_catalog.jsonb_typeof(config) operator(pg_catalog.!=) 'object' then
        raise exception 'loading config is not a jsonb object';
end if;

    _config_type = config operator(pg_catalog.->>) 'config_type';
    if _config_type is null or _config_type operator(pg_catalog.!=) 'loading' then
        raise exception 'invalid config_type for loading config';
end if;

    _implementation = config operator(pg_catalog.->>) 'implementation';
    if _implementation is null or _implementation not in ('row', 'document') then
        raise exception 'invalid loading config implementation';
end if;

    _column_name = config operator(pg_catalog.->>) 'column_name';
     if _column_name is null then
        raise exception 'invalid loading config, missing column_name';
end if;

    select count(*) operator(pg_catalog.>) 0 into strict _found
    from pg_catalog.pg_class k
        inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
        inner join pg_catalog.pg_attribute a on (k.oid operator(pg_catalog.=) a.attrelid)
        inner join pg_catalog.pg_type y on (a.atttypid operator(pg_catalog.=) y.oid)
    where n.nspname operator(pg_catalog.=) source_schema
        and k.relname operator(pg_catalog.=) source_table
        and a.attnum operator(pg_catalog.>) 0
        and a.attname operator(pg_catalog.=) _column_name
        and y.typname in ('text', 'varchar', 'char', 'bpchar', 'bytea');

    if not _found then
            raise exception 'column_name in config does not exist in the table: %', _column_name;
    end if;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;


