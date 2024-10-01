
-------------------------------------------------------------------------------
-- anthropic_generate
-- https://docs.anthropic.com/en/api/messages
CREATE OR REPLACE FUNCTION ai.anthropic_generate
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
) RETURNS jsonb
AS $python$
    #ADD-PYTHON-LIB-DIR
    import ai.anthropic
    import json

    client = ai.anthropic.make_client(plpy, api_key=_api_key, base_url=_base_url, timeout=_timeout, max_retries=_max_retries)

    _messages_1 = json.loads(_messages)

    args = {}
    if _system is not None:
        args["system"] = _system
    if _user_id is not None:
        args["metadata"] = {"user_id": _user_id}
    if _stop_sequences is not None:
        args["stop_sequences"] = _stop_sequences
    if _temperature is not None:
        args["temperature"] = _temperature
    if _tool_choice is not None:
        args["tool_choice"] = json.loads(_tool_choice)
    if _tools is not None:
        args["tools"] = json.loads(_tools)
    if _top_k is not None:
        args["top_k"] = _top_k
    if _top_p is not None:
        args["top_p"] = _top_p

    message = client.messages.create(model=_model, messages=_messages_1, max_tokens=_max_tokens, **args)
    return message.to_json()
$python$
LANGUAGE plpython3u VOLATILE PARALLEL SAFE SECURITY INVOKER
set search_path to pg_catalog, pg_temp ;
