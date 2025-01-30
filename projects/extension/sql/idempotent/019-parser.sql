-------------------------------------------------------------------------------
-- parser_pymupdf
create or replace function ai.parser_pymupdf() returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'implementation': 'pymupdf'
    , 'config_type': 'parser'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;
