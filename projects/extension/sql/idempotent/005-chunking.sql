
-------------------------------------------------------------------------------
-- chunking_character_text_splitter
create or replace function ai.chunking_character_text_splitter
( chunk_column name
, chunk_size int default 800
, chunk_overlap int default 400
, separator text default E'\n\n'
, is_separator_regex bool default false
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'character_text_splitter'
    , 'config_type': 'chunking'
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

-------------------------------------------------------------------------------
-- chunking_recursive_character_text_splitter
create or replace function ai.chunking_recursive_character_text_splitter
( chunk_column name
, chunk_size int default 800
, chunk_overlap int default 400
, separators text[] default array[E'\n\n', E'\n', '.', '?', '!', ' ', '']
, is_separator_regex bool default false
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'recursive_character_text_splitter'
    , 'config_type': 'chunking'
    , 'chunk_column': chunk_column
    , 'chunk_size': chunk_size
    , 'chunk_overlap': chunk_overlap
    , 'separators': separators
    , 'is_separator_regex': is_separator_regex
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_chunking
create or replace function ai._validate_chunking
( config jsonb
, source_schema name
, source_table name
) returns void
as $func$
declare
    _config_type text;
    _implementation text;
    _chunk_column text;
    _found bool;
begin
    if pg_catalog.jsonb_typeof(config) != 'object' then
        raise exception 'chunking config is not a jsonb object';
    end if;

    _config_type = config operator(pg_catalog.->>) 'config_type';
    if _config_type is null or _config_type != 'chunking' then
        raise exception 'invalid config_type for chunking config';
    end if;

    _implementation = config operator(pg_catalog.->>) 'implementation';
    if _implementation is null or _implementation not in ('character_text_splitter', 'recursive_character_text_splitter') then
        raise exception 'invalid chunking config implementation';
    end if;

    _chunk_column = config operator(pg_catalog.->>) 'chunk_column';

    select count(*) > 0 into strict _found
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
    inner join pg_catalog.pg_attribute a on (k.oid operator(pg_catalog.=) a.attrelid)
    inner join pg_catalog.pg_type y on (a.atttypid operator(pg_catalog.=) y.oid)
    where n.nspname operator(pg_catalog.=) source_schema
    and k.relname operator(pg_catalog.=) source_table
    and a.attnum operator(pg_catalog.>) 0
    and a.attname operator(pg_catalog.=) _chunk_column
    and y.typname in ('text', 'varchar', 'char', 'bpchar')
    ;
    if not _found then
        raise exception 'chunk column in config does not exist in the table: %', _chunk_column;
    end if;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;
