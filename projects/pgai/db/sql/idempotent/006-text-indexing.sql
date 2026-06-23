
-------------------------------------------------------------------------------
-- text_indexing_none
create or replace function ai.text_indexing_none() returns pg_catalog.jsonb
as $func$
    select jsonb_build_object
    ( 'implementation', 'none'
    , 'config_type', 'text_indexing'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- text_indexing_bm25
create or replace function ai.text_indexing_bm25
( text_config pg_catalog.text default 'english'
, k1 pg_catalog.float8 default 1.2
, b pg_catalog.float8 default 0.75
) returns pg_catalog.jsonb
as $func$
    select json_strip_nulls(json_build_object
    ( 'implementation', 'bm25'
    , 'config_type', 'text_indexing'
    , 'text_config', text_config
    , 'k1', k1
    , 'b', b
    ))
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_text_indexing_bm25
create or replace function ai._validate_text_indexing_bm25(config pg_catalog.jsonb) returns void
as $func$
declare
    _text_config pg_catalog.text;
    _k1 pg_catalog.float8;
    _b pg_catalog.float8;
begin
    -- Validate text_config is a valid regconfig (language configuration)
    _text_config = config operator(pg_catalog.->>) 'text_config';
    if _text_config is not null then
        begin
            perform _text_config::pg_catalog.regconfig;
        exception when others then
            raise exception 'invalid text_config: %. Must be a valid text search configuration (e.g., ''english'', ''simple'', ''french'')', _text_config;
        end;
    end if;

    -- Validate k1 is positive
    _k1 = (config operator(pg_catalog.->>) 'k1')::pg_catalog.float8;
    if _k1 is not null and _k1 operator(pg_catalog.<=) 0 then
        raise exception 'k1 must be a positive number, got: %', _k1;
    end if;

    -- Validate b is between 0 and 1
    _b = (config operator(pg_catalog.->>) 'b')::pg_catalog.float8;
    if _b is not null and (_b operator(pg_catalog.<) 0 or _b operator(pg_catalog.>) 1) then
        raise exception 'b must be between 0 and 1, got: %', _b;
    end if;
end
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_text_indexing
create or replace function ai._validate_text_indexing(config pg_catalog.jsonb) returns void
as $func$
declare
    _config_type pg_catalog.text;
    _implementation pg_catalog.text;
begin
    if pg_catalog.jsonb_typeof(config) operator(pg_catalog.!=) 'object' then
        raise exception 'text_indexing config is not a jsonb object';
    end if;

    _config_type = config operator(pg_catalog.->>) 'config_type';
    if _config_type is null or _config_type operator(pg_catalog.!=) 'text_indexing' then
        raise exception 'invalid config_type for text_indexing config';
    end if;
    _implementation = config operator(pg_catalog.->>) 'implementation';
    case _implementation
        when 'none' then
            -- ok
        when 'bm25' then
            perform ai._validate_text_indexing_bm25(config);
        else
            if _implementation is null then
                raise exception 'text_indexing implementation not specified';
            else
                raise exception 'invalid text_indexing implementation: "%"', _implementation;
            end if;
    end case;
end
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;

