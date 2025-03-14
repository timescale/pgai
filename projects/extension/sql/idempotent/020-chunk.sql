
-------------------------------------------------------------------------------
-- chunk_text
create or replace function ai.chunk_text
( input text
, chunk_size int default null
, chunk_overlap int default null
, separator text default null
, is_separator_regex bool default false
) returns table
( seq bigint
, chunk text
)
as $python$
    #ADD-PYTHON-LIB-DIR
    from langchain_text_splitters import CharacterTextSplitter
    
    args = {}
    if separator is not None:
        args["separator"] = separator
    if chunk_size is not None:
        args["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        args["chunk_overlap"] = chunk_overlap
    if is_separator_regex is not None:
        args["is_separator_regex"] = is_separator_regex
    
    chunker = CharacterTextSplitter(**args)
    for ix, chunk in enumerate(chunker.split_text(input)):
        yield ix, chunk
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- chunk_text_recursively
create or replace function ai.chunk_text_recursively
( input text
, chunk_size int default null
, chunk_overlap int default null
, separators text[] default null
, is_separator_regex bool default false
) returns table
( seq bigint
, chunk text
)
as $python$
    #ADD-PYTHON-LIB-DIR
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    args = {}
    if separators is not None:
        args["separators"] = separators
    if chunk_size is not None:
        args["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        args["chunk_overlap"] = chunk_overlap
    if is_separator_regex is not None:
        args["is_separator_regex"] = is_separator_regex
    
    chunker = RecursiveCharacterTextSplitter(**args)
    for ix, chunk in enumerate(chunker.split_text(input)):
        yield ix, chunk
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;
