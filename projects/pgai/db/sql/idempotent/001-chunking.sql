
-------------------------------------------------------------------------------
-- chunking_character_text_splitter
create or replace function ai.chunking_character_text_splitter
( chunk_size pg_catalog.int4 default 800
, chunk_overlap pg_catalog.int4 default 400
, separator pg_catalog.text default E'\n\n'
, is_separator_regex pg_catalog.bool default false
) returns pg_catalog.jsonb
as $func$
    select json_strip_nulls(json_build_object
    ( 'implementation', 'character_text_splitter'
    , 'config_type', 'chunking'
    , 'chunk_size', chunk_size
    , 'chunk_overlap', chunk_overlap
    , 'separator', separator
    , 'is_separator_regex', is_separator_regex
    ))
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- chunking_recursive_character_text_splitter
create or replace function ai.chunking_recursive_character_text_splitter
( chunk_size pg_catalog.int4 default 800
, chunk_overlap pg_catalog.int4 default 400
, separators pg_catalog.text[] default array[E'\n\n', E'\n', '.', '?', '!', ' ', '']
, is_separator_regex pg_catalog.bool default false
) returns pg_catalog.jsonb
as $func$
    select json_strip_nulls(json_build_object
    ( 'implementation', 'recursive_character_text_splitter'
    , 'config_type', 'chunking'
    , 'chunk_size', chunk_size
    , 'chunk_overlap', chunk_overlap
    , 'separators', separators
    , 'is_separator_regex', is_separator_regex
    ))
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- chunking_none
create or replace function ai.chunking_none() returns pg_catalog.jsonb
as $func$
    select json_build_object
    ( 'implementation', 'none'
    , 'config_type', 'chunking'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_chunking
create or replace function ai._validate_chunking
( config pg_catalog.jsonb ) returns void
as $func$
declare
    _config_type pg_catalog.text;
    _implementation pg_catalog.text;
begin
    if pg_catalog.jsonb_typeof(config) operator(pg_catalog.!=) 'object' then
        raise exception 'chunking config is not a jsonb object';
    end if;

    _config_type = config operator(pg_catalog.->>) 'config_type';
    if _config_type is null or _config_type operator(pg_catalog.!=) 'chunking' then
        raise exception 'invalid config_type for chunking config';
    end if;

    _implementation = config operator(pg_catalog.->>) 'implementation';
    if _implementation is null or _implementation not in ('character_text_splitter', 'recursive_character_text_splitter', 'none') then
        raise exception 'invalid chunking config implementation';
    end if;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;
