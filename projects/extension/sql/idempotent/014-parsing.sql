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
