-------------------------------------------------------------------------------
-- parser_auto
create or replace function ai.parser_auto() returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'implementation': 'auto'
    , 'config_type': 'parser'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;