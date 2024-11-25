-------------------------------------------------------------------------------
-- voyageai_embed
-- generate an embedding from a text value
-- https://docs.voyageai.com/reference/embeddings-api
create or replace function ai.voyageai_embed
( model text
, input_text text
, input_type text default null
, api_key text default null
, api_key_name text default null
) returns @extschema:vector@.vector
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.voyageai
    import ai.secrets
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.voyageai.DEFAULT_KEY_NAME, SD)
    for tup in ai.voyageai.embed(model, [input_text], api_key=api_key_resolved):
        return tup[1]
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- voyageai_embed
-- generate embeddings from an array of text values
-- https://docs.voyageai.com/reference/embeddings-api
create or replace function ai.voyageai_embed
( model text
, input_texts text[]
, api_key text default null
, api_key_name text default null
, input_type text default null
) returns table
( "index" int
, embedding @extschema:vector@.vector
)
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.voyageai
    import ai.secrets
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.voyageai.DEFAULT_KEY_NAME, SD)
    for tup in ai.voyageai.embed(model, input_texts, api_key=api_key_resolved):
        yield tup
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;
