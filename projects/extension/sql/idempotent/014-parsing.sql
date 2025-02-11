-------------------------------------------------------------------------------
-- parsing_auto
create or replace function ai.parsing_auto() returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'implementation': 'auto'
    , 'config_type': 'parsing'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- parsing_none
create or replace function ai.parsing_none() returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'implementation': 'none'
    , 'config_type': 'parsing'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- parser_pymupdf
create or replace function ai.parsing_pymupdf() returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'implementation': 'pymupdf'
    , 'config_type': 'parsing'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_parsing
create or replace function ai._validate_parsing
( config pg_catalog.jsonb  -- has to contain both loading and parsing config
) returns void
as $func$
declare
    _parsing_config pg_catalog.jsonb;
    _loading_config pg_catalog.jsonb;
    _config_type pg_catalog.text;
    _implementation pg_catalog.text;
    _loading_implementation pg_catalog.text;
    _column_type pg_catalog.text;
begin
    -- Get the parsing and loading configs
    _parsing_config = config operator(pg_catalog.->) 'parsing';
    _loading_config = config operator(pg_catalog.->) 'loading';

    -- Basic structure validation
    if pg_catalog.jsonb_typeof(_parsing_config) operator(pg_catalog.!=) 'object' then
        raise exception 'parsing config is not a jsonb object';
    end if;

    -- Validate config_type
    _config_type = _parsing_config operator(pg_catalog.->>) 'config_type';
    if _config_type is null or _config_type operator(pg_catalog.!=) 'parsing' then
        raise exception 'invalid config_type for parsing config';
    end if;

    -- Get implementations
    _implementation = _parsing_config operator(pg_catalog.->>) 'implementation';
    _loading_implementation = _loading_config operator(pg_catalog.->>) 'implementation';

    if _implementation is null then
        raise exception 'invalid parsing config implementation';
    end if;

    -- Get the column type once
    select y.typname 
    into _column_type
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
    inner join pg_catalog.pg_attribute a on (k.oid operator(pg_catalog.=) a.attrelid)
    inner join pg_catalog.pg_type y on (a.atttypid operator(pg_catalog.=) y.oid)
    where n.nspname operator(pg_catalog.=) (config operator(pg_catalog.->>) 'source_schema')
    and k.relname operator(pg_catalog.=) (config operator(pg_catalog.->>) 'source_table')
    and a.attnum operator(pg_catalog.>) 0
    and a.attname operator(pg_catalog.=) (_loading_config operator(pg_catalog.->>) 'column_name');

    -- Validate all combinations
    if _implementation = 'none' and _column_type = 'bytea' then
        raise exception 'cannot use parsing_none with bytea columns';
    end if;

    if _loading_implementation = 'document' and _implementation = 'none' then
        raise exception 'cannot use parsing_none with document loading';
    end if;

    if _implementation = 'pymupdf' 
       and _loading_implementation = 'row' 
       and _column_type in ('text', 'varchar', 'char', 'bpchar') then
        raise exception 'cannot use parsing_pymupdf with text columns';
    end if;

end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp;