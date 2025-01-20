--FEATURE-FLAG: text_to_sql

-------------------------------------------------------------------------------
-- _text_to_sql_cohere
create function ai._text_to_sql_cohere
( question text
, catalog_name text default 'default'
, config jsonb default null -- TODO: use this for LLM configuration
) returns jsonb
as $func$
declare
begin
    raise exception 'not implemented yet';
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;