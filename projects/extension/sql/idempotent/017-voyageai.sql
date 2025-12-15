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
, verbose boolean default false
) returns @extschema:vector@.vector
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.voyageai
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.voyageai.DEFAULT_KEY_NAME, SD)
    with ai.utils.VerboseRequestTrace(plpy, "voyageai.embed()", verbose):
        args = {}
        if input_type is not None:
            args["input_type"] = input_type
    for tup in ai.voyageai.embed(model, [input_text], api_key=api_key_resolved, **args):
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
, input_type text default null
, api_key text default null
, api_key_name text default null
, verbose boolean default false
) returns table
( "index" int
, embedding @extschema:vector@.vector
)
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.voyageai
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.voyageai.DEFAULT_KEY_NAME, SD)
    args = {}
    if input_type is not None:
        args["input_type"] = input_type
    
    with ai.utils.VerboseRequestTrace(plpy, "voyageai.embed()", verbose):
        results = ai.voyageai.embed(model, input_texts, api_key=api_key_resolved, **args)

    for tup in results:
        yield tup
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- voyageai_rerank
-- https://docs.voyageai.com/docs/reranker
create or replace function ai.voyageai_rerank
( model text
, query text
, documents text[]
, api_key text default null
, api_key_name text default null
, top_k integer default null
, truncation boolean default null
, verbose boolean default false
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.voyageai
    import ai.secrets
    import ai.utils
    import json
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.voyageai.DEFAULT_KEY_NAME, SD)

    args = {}
    if top_k is not None:
        args["top_k"] = top_k
    if truncation is not None:
        args["truncation"] = truncation

    with ai.utils.VerboseRequestTrace(plpy, "voyageai.rerank()", verbose):
        response = ai.voyageai.rerank(model, query, documents, api_key_resolved, **args)

    return json.dumps(response)
$python$ language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- voyageai_rerank_simple
-- https://docs.voyageai.com/docs/reranker
create or replace function ai.voyageai_rerank_simple
( model text
, query text
, documents text[]
, api_key text default null
, api_key_name text default null
, top_k integer default null
, truncation boolean default null
, verbose boolean default false
) returns table
( "index" int
, "document" text
, relevance_score float8
)
as $func$
select
  x."index"
, d.document
, x.relevance_score
from pg_catalog.jsonb_to_recordset
(
    ai.voyageai_rerank
    ( model
    , query
    , documents
    , api_key=>api_key
    , api_key_name=>api_key_name
    , top_k=>top_k
    , truncation=>truncation
    , verbose=>"verbose"
    ) operator(pg_catalog.->) 'results'
) x("index" int, relevance_score float8)
inner join unnest(documents) with ordinality d (document, ord)
on (x."index" = (d.ord - 1))
$func$ language sql immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;
