-------------------------------------------------------------------------------
-- ai 0.3.0


-------------------------------------------------------------------------------
-- anthropic_generate
-- https://docs.anthropic.com/en/api/messages
create function @extschema@.anthropic_generate
( _model text
, _messages jsonb
, _max_tokens int default 1024
, _api_key text default null
, _base_url text default null
, _timeout float8 default null
, _max_retries int default null
, _system text default null
, _user_id text default null
, _stop_sequences text[] default null
, _temperature float8 default null
, _tool_choice jsonb default null
, _tools jsonb default null
, _top_k int default null
, _top_p float8 default null
) returns jsonb
as $func$
_api_key_1 = _api_key
if _api_key_1 is None:
    r = plpy.execute("select pg_catalog.current_setting('ai.anthropic_api_key', true) as api_key")
    if len(r) >= 0:
        _api_key_1 = r[0]["api_key"]
if _api_key_1 is None:
    plpy.error("missing api key")

import anthropic

args = {}
if _base_url is not None:
    args["base_url"] = _base_url
if _timeout is not None:
    args["timeout"] = _timeout
if _max_retries is not None:
    args["max_retries"] = _max_retries
client = anthropic.Anthropic(api_key=_api_key_1, **args)

import json
_messages_1 = json.loads(_messages)

args = {}
if _system is not None:
    args["system"] = _system
if _user_id is not None:
    args["metadata"] = {"user_id", _user_id}
if _stop_sequences is not None:
    args["stop_sequences"] = _stop_sequences
if _temperature is not None:
    args["temperature"] = _temperature
if _tool_choice is not None:
    args["tool_choice"] = json.dumps(_tool_choice)
if _tools is not None:
    args["tools"] = json.dumps(_tools)
if _top_k is not None:
    args["top_k"] = _top_k
if _top_p is not None:
    args["top_p"] = _top_p

message = client.messages.create(model=_model, messages=_messages_1, max_tokens=_max_tokens, **args)
return message.to_json()
$func$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_list_models
-- https://docs.cohere.com/reference/list-models
create function @extschema@.cohere_list_models
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
as $func$
_api_key_1 = _api_key
if _api_key_1 is None:
    r = plpy.execute("select pg_catalog.current_setting('ai.cohere_api_key', true) as api_key")
    if len(r) >= 0:
        _api_key_1 = r[0]["api_key"]
if _api_key_1 is None:
    plpy.error("missing api key")
import cohere
client = cohere.Client(_api_key_1)
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
$func$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_embed
-- https://docs.cohere.com/reference/embed-1
create function @extschema@.cohere_embed
( _model text
, _input text
, _api_key text default null
, _input_type text default null
, _truncate text default null
) returns vector
as $func$
_api_key_1 = _api_key
if _api_key_1 is None:
    r = plpy.execute("select pg_catalog.current_setting('ai.cohere_api_key', true) as api_key")
    if len(r) >= 0:
        _api_key_1 = r[0]["api_key"]
if _api_key_1 is None:
    plpy.error("missing api key")

import cohere
client = cohere.Client(_api_key_1)

args={}
if _input_type is not None:
    args["input_type"] = _input_type
if _truncate is not None:
    args["truncate"] = _truncate

response = client.embed(texts=[_input], model=_model, **args)
return response.embeddings[0]
$func$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;
