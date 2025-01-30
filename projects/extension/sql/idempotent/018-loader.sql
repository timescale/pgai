-------------------------------------------------------------------------------
-- loader_file_loader
create or replace function ai.loader_file_loader
( url_column pg_catalog.text
) returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'implementation': 'file_loader'
    , 'config_type': 'loader'
    , 'url_column': url_column
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;
