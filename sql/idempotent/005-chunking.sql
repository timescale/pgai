
-------------------------------------------------------------------------------
-- chunking_character_text_splitter
create or replace function ai.chunking_character_text_splitter
( chunk_column name
, chunk_size int
, chunk_overlap int
, separator text default E'\n\n'
, is_separator_regex bool default false
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'character_text_splitter'
    , 'chunk_column': chunk_column
    , 'chunk_size': chunk_size
    , 'chunk_overlap': chunk_overlap
    , 'separator': separator
    , 'is_separator_regex': is_separator_regex
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-- TODO: add recursive character text splitter

-------------------------------------------------------------------------------
-- _validate_chunking_character_text_splitter
create or replace function ai._validate_chunking_character_text_splitter
( config jsonb
, source_schema name
, source_table name
) returns void
as $func$
declare
    _chunk_column text;
    _found bool;
begin
    select config operator(pg_catalog.->>) 'chunk_column'
    into strict _chunk_column
    ;

    select count(*) > 0 into strict _found
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace = n.oid)
    inner join pg_catalog.pg_attribute a on (k.oid = a.attrelid)
    where n.nspname operator(pg_catalog.=) source_schema
    and k.relname operator(pg_catalog.=) source_table
    and a.attnum operator(pg_catalog.>) 0
    and a.attname operator(pg_catalog.=) _chunk_column
    ;
    if not _found then
        raise exception 'chunk column in config does not exist in the table: %', _chunk_column;
    end if;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;
