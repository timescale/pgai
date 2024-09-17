-------------------------------------------------------------------------------
-- anthropic_generate
-- https://docs.anthropic.com/en/api/messages
create or replace function ai.anthropic_generate
( model text
, messages jsonb
, max_tokens int default 1024
, api_key text default null
, api_key_name text default null
, base_url text default null
, timeout float8 default null
, max_retries int default null
, system_prompt text default null
, user_id text default null
, stop_sequences text[] default null
, temperature float8 default null
, tool_choice jsonb default null
, tools jsonb default null
, top_k int default null
, top_p float8 default null
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.anthropic
    import ai.secrets
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.anthropic.DEFAULT_KEY_NAME, SD)
    client = ai.anthropic.make_client(api_key=api_key_resolved, base_url=base_url, timeout=timeout, max_retries=max_retries)

    import json
    messages_1 = json.loads(messages)

    args = {}
    if system_prompt is not None:
        args["system"] = system_prompt
    if user_id is not None:
        args["metadata"] = {"user_id", user_id}
    if stop_sequences is not None:
        args["stop_sequences"] = stop_sequences
    if temperature is not None:
        args["temperature"] = temperature
    if tool_choice is not None:
        args["tool_choice"] = json.loads(tool_choice)
    if tools is not None:
        args["tools"] = json.loads(tools)
    if top_k is not None:
        args["top_k"] = top_k
    if top_p is not None:
        args["top_p"] = top_p

    message = client.messages.create(model=model, messages=messages_1, max_tokens=max_tokens, **args)
    return message.to_json()
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;
