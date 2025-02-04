-------------------------------------------------------------------------------
-- cohere_list_models
-- https://docs.cohere.com/reference/list-models
create or replace function ai.cohere_list_models
( api_key text default null
, api_key_name text default null
, endpoint text default null
, default_only bool default null
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
    import ai.secrets
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    args = {}
    if endpoint is not None:
        args["endpoint"] = endpoint
    if default_only is not None:
        args["default_only"] = default_only
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
create or replace function ai.cohere_tokenize(model text, text_input text, api_key text default null, api_key_name text default null) returns int[]
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.cohere
    import ai.secrets
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    response = client.tokenize(text=text_input, model=model)
    return response.tokens
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_detokenize
-- https://docs.cohere.com/reference/detokenize
create or replace function ai.cohere_detokenize(model text, tokens int[], api_key text default null, api_key_name text default null) returns text
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.cohere
    import ai.secrets
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    response = client.detokenize(tokens=tokens, model=model)
    return response.text
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_embed
-- https://docs.cohere.com/reference/embed-1
create or replace function ai.cohere_embed
( model text
, input_text text
, api_key text default null
, api_key_name text default null
, input_type text default null
, truncate_long_inputs text default null
) returns @extschema:vector@.vector
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.cohere
    import ai.secrets
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    args={}
    if input_type is not None:
        args["input_type"] = input_type
    if truncate_long_inputs is not None:
        args["truncate"] = truncate_long_inputs
    response = client.embed(texts=[input_text], model=model, embedding_types=["float"], **args)
    return response.embeddings.float[0]
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_classify
-- https://docs.cohere.com/reference/classify
create or replace function ai.cohere_classify
( model text
, inputs text[]
, api_key text default null
, api_key_name text default null
, examples jsonb default null
, truncate_long_inputs text default null
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.cohere
    import ai.secrets
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    import json
    args = {}
    if examples is not None:
        args["examples"] = json.loads(examples)
    if truncate_long_inputs is not None:
        args["truncate"] = truncate_long_inputs

    response = client.classify(inputs=inputs, model=model, **args)
    return response.json()
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_classify_simple
-- https://docs.cohere.com/reference/classify
create or replace function ai.cohere_classify_simple
( model text
, inputs text[]
, api_key text default null
, api_key_name text default null
, examples jsonb default null
, truncate_long_inputs text default null
) returns table
( input text
, prediction text
, confidence float8
)
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.cohere
    import ai.secrets
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    import json
    args = {}
    if examples is not None:
        args["examples"] = json.loads(examples)
    if truncate_long_inputs is not None:
        args["truncate"] = truncate_long_inputs
    response = client.classify(inputs=inputs, model=model, **args)
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
( model text
, query text
, documents text[]
, api_key text default null
, api_key_name text default null
, top_n integer default null
, max_tokens_per_doc int default null
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.cohere
    import ai.secrets
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    args = {}
    if top_n is not None:
        args["top_n"] = top_n
    if max_tokens_per_doc is not None:
        args["max_tokens_per_doc"] = max_tokens_per_doc

    response = client.rerank(model=model, query=query, documents=documents, **args)
    return response.json()
$python$ language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_rerank_simple
-- https://docs.cohere.com/reference/rerank
create or replace function ai.cohere_rerank_simple
( model text
, query text
, documents text[]
, api_key text default null
, api_key_name text default null
, top_n integer default null
, max_tokens_per_doc int default null
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
    ai.cohere_rerank
    ( model
    , query
    , documents
    , api_key=>api_key
    , api_key_name=>api_key_name
    , top_n=>top_n
    , max_tokens_per_doc=>max_tokens_per_doc
    ) operator(pg_catalog.->) 'results'
) x("index" int, relevance_score float8)
inner join unnest(documents) with ordinality d (document, ord)
on (x."index" = (d.ord - 1))
$func$ language sql immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_chat_complete
-- https://docs.cohere.com/reference/chat
create or replace function ai.cohere_chat_complete
( model text
, messages jsonb
, api_key text default null
, api_key_name text default null
, tools jsonb default null
, documents jsonb default null
, citation_options jsonb default null
, response_format jsonb default null
, safety_mode text default null
, max_tokens int default null
, stop_sequences text[] default null
, temperature float8 default null
, seed int default null
, frequency_penalty float8 default null
, presence_penalty float8 default null
, k int default null
, p float8 default null
, logprobs boolean default null
, tool_choice text default null
, strict_tools bool default null
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.cohere
    import ai.secrets
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    import json
    args = {}

    if tools is not None:
        args["tools"] = json.loads(tools)
    if documents is not None:
        args["documents"] = json.loads(documents)
    if citation_options is not None:
        args["citation_options"] = json.loads(citation_options)
    if response_format is not None:
        args["response_format"] = json.loads(response_format)
    if safety_mode is not None:
        args["safety_mode"] = safety_mode
    if max_tokens is not None:
        args["max_tokens"] = max_tokens
    if stop_sequences is not None:
        args["stop_sequences"] = stop_sequences
    if temperature is not None:
        args["temperature"] = temperature
    if seed is not None:
        args["seed"] = seed
    if frequency_penalty is not None:
        args["frequency_penalty"] = frequency_penalty
    if presence_penalty is not None:
        args["presence_penalty"] = presence_penalty
    if k is not None:
        args["k"] = k
    if p is not None:
        args["p"] = p
    if logprobs is not None:
        args["logprobs"] = logprobs
    if tool_choice is not None:
        args["tool_choice"] = tool_choice
    if strict_tools is not None:
        args["strict_tools"] = strict_tools

    response = client.chat(model=model, messages=json.loads(messages), **args)
    return response.json()
$python$ language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;