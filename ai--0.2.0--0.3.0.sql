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
