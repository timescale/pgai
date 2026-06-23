-------------------------------------------------------------------------------
-- loading_column
create or replace function ai.loading_column
( column_name pg_catalog.name
, retries pg_catalog.int4 default 6)
returns pg_catalog.jsonb
as $func$
    select json_build_object
    ( 'implementation', 'column'
    , 'config_type', 'loading'
    , 'column_name', column_name
    , 'retries', retries
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- loading_uri
create or replace function ai.loading_uri
( column_name pg_catalog.name
, retries pg_catalog.int4 default 6
, aws_role_arn pg_catalog.text default null)
returns pg_catalog.jsonb
as $func$
    select json_strip_nulls(json_build_object
    ( 'implementation', 'uri'
    , 'config_type', 'loading'
    , 'column_name', column_name
    , 'retries', retries
    , 'aws_role_arn', aws_role_arn
    ))
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
    _column_name pg_catalog.name;
    _found pg_catalog.bool;
    _column_type pg_catalog.text;
begin
    if pg_catalog.jsonb_typeof(config) operator(pg_catalog.!=) 'object' then
        raise exception 'loading config is not a jsonb object';
end if;

    _config_type = config operator(pg_catalog.->>) 'config_type';
    if _config_type is null or _config_type operator(pg_catalog.!=) 'loading' then
        raise exception 'invalid config_type for loading config';
end if;

    _implementation = config operator(pg_catalog.->>) 'implementation';
    if _implementation is null or _implementation not in ('column', 'uri') then
        raise exception 'invalid loading config implementation';
end if;

    _column_name = config operator(pg_catalog.->>) 'column_name';
     if _column_name is null then
        raise exception 'invalid loading config, missing column_name';
end if;

    if (config operator(pg_catalog.->>) 'retries') is null or (config operator(pg_catalog.->>) 'retries')::int < 0 then
        raise exception 'invalid loading config, retries must be a non-negative integer';
end if;
    if (config operator(pg_catalog.->>) 'aws_role_arn') is not null and (config operator(pg_catalog.->>) 'aws_role_arn') not like 'arn:aws:iam::%:role/%' then
        raise exception 'invalid loading config, aws_role_arn must match arn:aws:iam::*:role/*';
end if;

    select y.typname into _column_type
    from pg_catalog.pg_class k
        inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
        inner join pg_catalog.pg_attribute a on (k.oid operator(pg_catalog.=) a.attrelid)
        inner join pg_catalog.pg_type y on (a.atttypid operator(pg_catalog.=) y.oid)
    where n.nspname operator(pg_catalog.=) source_schema
        and k.relname operator(pg_catalog.=) source_table
        and a.attnum operator(pg_catalog.>) 0
        and a.attname operator(pg_catalog.=) _column_name
        and not a.attisdropped;

    if _column_type is null then
            raise exception 'column_name in config does not exist in the table: %', _column_name;
    end if;

    if _column_type not in ('text', 'varchar', 'char', 'bpchar', 'bytea') then
            raise exception 'column_name % in config is of invalid type %. Supported types are: text, varchar, char, bpchar, bytea', _column_name, _column_type;
    end if;

    if _implementation = 'uri' and _column_type not in ('text', 'varchar', 'char', 'bpchar') then
        raise exception 'the type of the column `%` in config is not compatible with `uri` loading '
       'implementation (type should be either text, varchar, char, bpchar, or bytea)', _column_name;
    end if;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;
