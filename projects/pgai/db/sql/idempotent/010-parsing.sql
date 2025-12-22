-------------------------------------------------------------------------------
-- parsing_auto
create or replace function ai.parsing_auto() returns pg_catalog.jsonb
as $func$
    select json_build_object
    ( 'implementation', 'auto'
    , 'config_type', 'parsing'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- parsing_none
create or replace function ai.parsing_none() returns pg_catalog.jsonb
as $func$
    select json_build_object
    ( 'implementation', 'none'
    , 'config_type', 'parsing'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- parser_pymupdf
create or replace function ai.parsing_pymupdf() returns pg_catalog.jsonb
as $func$
    select json_build_object
    ( 'implementation', 'pymupdf'
    , 'config_type', 'parsing'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- parser_docling
create or replace function ai.parsing_docling() returns pg_catalog.jsonb
as $func$
    select json_build_object
    ( 'implementation', 'docling'
    , 'config_type', 'parsing'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_parsing
create or replace function ai._validate_parsing
( parsing pg_catalog.jsonb
, loading pg_catalog.jsonb
, source_schema pg_catalog.name
, source_table pg_catalog.name
) returns void
as $func$
declare
    _column_type pg_catalog.name;
    _config_type pg_catalog.text;
    _loading_implementation pg_catalog.text;
    _parsing_implementation pg_catalog.text;
begin
    -- Basic structure validation
    if pg_catalog.jsonb_typeof(parsing) operator(pg_catalog.!=) 'object' then
        raise exception 'parsing config is not a jsonb object';
    end if;

    -- Validate config_type
    _config_type = parsing operator(pg_catalog.->>) 'config_type';
    if _config_type is null or _config_type operator(pg_catalog.!=) 'parsing' then
        raise exception 'invalid config_type for parsing config';
    end if;

    -- Get implementations
    _loading_implementation = loading operator(pg_catalog.->>) 'implementation';
    -- Skip validation of loading implementation since it's done in _validate_loading

    _parsing_implementation = parsing operator(pg_catalog.->>) 'implementation';
    if _parsing_implementation not in ('auto', 'none', 'pymupdf', 'docling') then
        raise exception 'invalid parsing config implementation';
    end if;

    -- Get the column type once
    select y.typname 
    into _column_type
    from pg_catalog.pg_class k
        inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
        inner join pg_catalog.pg_attribute a on (k.oid operator(pg_catalog.=) a.attrelid)
        inner join pg_catalog.pg_type y on (a.atttypid operator(pg_catalog.=) y.oid)
    where n.nspname operator(pg_catalog.=) source_schema
    and k.relname operator(pg_catalog.=) source_table
    and a.attnum operator(pg_catalog.>) 0
    and a.attname operator(pg_catalog.=) (loading operator(pg_catalog.->>) 'column_name');

    -- Validate all combinations
    if _parsing_implementation = 'none' and _column_type = 'bytea' then
        raise exception 'cannot use parsing_none with bytea columns';
    end if;

    if _loading_implementation = 'column' and _parsing_implementation in ('pymupdf', 'docling')
       and _column_type != 'bytea' then
        raise exception 'parsing_% must be used with a bytea column', _parsing_implementation;
    end if;

end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp;
