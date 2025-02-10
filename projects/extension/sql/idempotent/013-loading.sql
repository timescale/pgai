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
