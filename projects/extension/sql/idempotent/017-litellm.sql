-------------------------------------------------------------------------------
-- litellm_embed
-- generate an embedding from a text value
create or replace function ai.litellm_embed
( model text
, input_text text
, api_key text default null
, api_key_name text default null
, extra_options jsonb default null
) returns @extschema:vector@.vector
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.litellm
    import ai.secrets
    options = {}
    if extra_options is not None:
        import json
        options = {k: v for k, v in json.loads(extra_options).items()}

    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, None, SD)
    for tup in ai.litellm.embed(model, [input_text], api_key=api_key_resolved, **options):
        return tup[1]
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- litellm_embed
-- generate embeddings from an array of text values
create or replace function ai.litellm_embed
( model text
, input_texts text[]
, api_key text default null
, api_key_name text default null
, extra_options jsonb default null
) returns table
( "index" int
, embedding @extschema:vector@.vector
)
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.litellm
    import ai.secrets
    options = {}
    if extra_options is not None:
        import json
        options = {k: v for k, v in json.loads(extra_options).items()}

    plpy.log("options", options)

    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, None, SD)
    for tup in ai.litellm.embed(model, input_texts, api_key=api_key_resolved, **options):
        yield tup
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;
