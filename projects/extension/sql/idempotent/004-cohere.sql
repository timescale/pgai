
-------------------------------------------------------------------------------
-- cohere_list_models
-- https://docs.cohere.com/reference/list-models
create or replace function ai.cohere_list_models
( _api_key text default null
, _endpoint text default null
, _default_only bool default null
)
returns table
( "name" text
, endpoints text[]
, finetuned bool
, context_length int
, tokenizer_url text
, default_endpoints text[]
)
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.cohere
    client = ai.cohere.make_client(plpy, _api_key)

    args = {}
    if _endpoint is not None:
        args["endpoint"] = _endpoint
    if _default_only is not None:
        args["default_only"] = _default_only
    page_token = None
    while True:
        resp = client.models.list(page_size=1000, page_token=page_token, **args)
        for model in resp.models:
            yield (model.name, model.endpoints, model.finetuned, model.context_length, model.tokenizer_url, model.default_endpoints)
        page_token = resp.next_page_token
        if page_token is None:
            break
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_tokenize
-- https://docs.cohere.com/reference/tokenize
create or replace function ai.cohere_tokenize(_model text, _text text, _api_key text default null) returns int[]
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.cohere
    client = ai.cohere.make_client(plpy, _api_key)

    response = client.tokenize(text=_text, model=_model)
    return response.tokens
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_detokenize
-- https://docs.cohere.com/reference/detokenize
create or replace function ai.cohere_detokenize(_model text, _tokens int[], _api_key text default null) returns text
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.cohere
    client = ai.cohere.make_client(plpy, _api_key)

    response = client.detokenize(tokens=_tokens, model=_model)
    return response.text
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_embed
-- https://docs.cohere.com/reference/embed-1
create or replace function ai.cohere_embed
( _model text
, _input text
, _api_key text default null
, _input_type text default null
, _truncate text default null
) returns @extschema:vector@.vector
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.cohere
    client = ai.cohere.make_client(plpy, _api_key)

    args={}
    if _input_type is not None:
        args["input_type"] = _input_type
    if _truncate is not None:
        args["truncate"] = _truncate
    response = client.embed(texts=[_input], model=_model, **args)
    return response.embeddings[0]
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_classify
-- https://docs.cohere.com/reference/classify
create or replace function ai.cohere_classify
( _model text
, _inputs text[]
, _api_key text default null
, _examples jsonb default null
, _truncate text default null
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.cohere
    client = ai.cohere.make_client(plpy, _api_key)

    import json
    args = {}
    if _examples is not None:
        args["examples"] = json.loads(_examples)
    if _truncate is not None:
        args["truncate"] = _truncate

    response = client.classify(inputs=_inputs, model=_model, **args)
    return response.json()
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_classify_simple
-- https://docs.cohere.com/reference/classify
create or replace function ai.cohere_classify_simple
( _model text
, _inputs text[]
, _api_key text default null
, _examples jsonb default null
, _truncate text default null
) returns table
( input text
, prediction text
, confidence float8
)
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.cohere
    client = ai.cohere.make_client(plpy, _api_key)
    import json
    args = {}
    if _examples is not None:
        args["examples"] = json.loads(_examples)
    if _truncate is not None:
        args["truncate"] = _truncate
    response = client.classify(inputs=_inputs, model=_model, **args)
    for x in response.classifications:
        yield x.input, x.prediction, x.confidence
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_rerank
-- https://docs.cohere.com/reference/rerank
create or replace function ai.cohere_rerank
( _model text
, _query text
, _documents jsonb
, _api_key text default null
, _top_n integer default null
, _rank_fields text[] default null
, _return_documents bool default null
, _max_chunks_per_doc int default null
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.cohere
    client = ai.cohere.make_client(plpy, _api_key)
    import json
    args = {}
    if _top_n is not None:
        args["top_n"] = _top_n
    if _rank_fields is not None:
        args["rank_fields"] = _rank_fields
    if _return_documents is not None:
        args["return_documents"] = _return_documents
    if _max_chunks_per_doc is not None:
        args["max_chunks_per_doc"] = _max_chunks_per_doc
    _documents_1 = json.loads(_documents)
    response = client.rerank(model=_model, query=_query, documents=_documents_1, **args)
    return response.json()
$python$ language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_rerank_simple
-- https://docs.cohere.com/reference/rerank
create or replace function ai.cohere_rerank_simple
( _model text
, _query text
, _documents jsonb
, _api_key text default null
, _top_n integer default null
, _max_chunks_per_doc int default null
) returns table
( "index" int
, "document" jsonb
, relevance_score float8
)
as $func$
select *
from pg_catalog.jsonb_to_recordset
(
    ai.cohere_rerank
    ( _model
    , _query
    , _documents
    , _api_key=>_api_key
    , _top_n=>_top_n
    , _return_documents=>true
    , _max_chunks_per_doc=>_max_chunks_per_doc
    ) operator(pg_catalog.->) 'results'
) x("index" int, "document" jsonb, relevance_score float8)
$func$ language sql immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_chat_complete
-- https://docs.cohere.com/reference/chat
create or replace function ai.cohere_chat_complete
( _model text
, _message text
, _api_key text default null
, _preamble text default null
, _chat_history jsonb default null
, _conversation_id text default null
, _prompt_truncation text default null
, _connectors jsonb default null
, _search_queries_only bool default null
, _documents jsonb default null
, _citation_quality text default null
, _temperature float8 default null
, _max_tokens int default null
, _max_input_tokens int default null
, _k int default null
, _p float8 default null
, _seed int default null
, _stop_sequences text[] default null
, _frequency_penalty float8 default null
, _presence_penalty float8 default null
, _tools jsonb default null
, _tool_results jsonb default null
, _force_single_step bool default null
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.cohere
    client = ai.cohere.make_client(plpy, _api_key)

    import json
    args = {}
    if _preamble is not None:
        args["preamble"] = _preamble
    if _chat_history is not None:
        args["chat_history"] = json.loads(_chat_history)
    if _conversation_id is not None:
        args["conversation_id"] = _conversation_id
    if _prompt_truncation is not None:
        args["prompt_truncation"] = _prompt_truncation
    if _connectors is not None:
        args["connectors"] = json.loads(_connectors)
    if _search_queries_only is not None:
        args["search_queries_only"] = _search_queries_only
    if _documents is not None:
        args["documents"] = json.loads(_documents)
    if _citation_quality is not None:
        args["citation_quality"] = _citation_quality
    if _temperature is not None:
        args["temperature"] = _temperature
    if _max_tokens is not None:
        args["max_tokens"] = _max_tokens
    if _max_input_tokens is not None:
        args["max_input_tokens"] = _max_input_tokens
    if _k is not None:
        args["k"] = _k
    if _p is not None:
        args["p"] = _p
    if _seed is not None:
        args["seed"] = _seed
    if _stop_sequences is not None:
        args["stop_sequences"] = _stop_sequences
    if _frequency_penalty is not None:
        args["frequency_penalty"] = _frequency_penalty
    if _presence_penalty is not None:
        args["presence_penalty"] = _presence_penalty
    if _tools is not None:
        args["tools"] = json.loads(_tools)
    if _tool_results is not None:
        args["tool_results"] = json.loads(_tool_results)
    if _force_single_step is not None:
        args["force_single_step"] = _force_single_step

    response = client.chat(model=_model, message=_message, **args)
    return response.json()
$python$ language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;
