-------------------------------------------------------------------------------
-- loader_file_loader
create or replace function ai.loader_from_document
( file_uri_column pg_catalog.text default 'url'
) returns pg_catalog.jsonb
as $func$
    select json_object
    ( 'implementation': 'document'
    , 'config_type': 'loader'
    , 'file_uri_column': file_uri_column
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;