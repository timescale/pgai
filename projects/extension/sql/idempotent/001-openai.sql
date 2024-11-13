
-------------------------------------------------------------------------------
-- openai_tokenize
-- encode text as tokens for a given model
-- https://github.com/openai/tiktoken/blob/main/README.md
create or replace function ai.openai_tokenize(_model text, _text text) returns int[]
as $python$
    #ADD-PYTHON-LIB-DIR
    import tiktoken
    encoding = tiktoken.encoding_for_model(_model)
    tokens = encoding.encode(_text)
    return tokens
$python$
language plpython3u strict immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_detokenize
-- decode tokens for a given model back into text
-- https://github.com/openai/tiktoken/blob/main/README.md
create or replace function ai.openai_detokenize(_model text, _tokens int[]) returns text
as $python$
    #ADD-PYTHON-LIB-DIR
    import tiktoken
    encoding = tiktoken.encoding_for_model(_model)
    content = encoding.decode(_tokens)
    return content
$python$
language plpython3u strict immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_client_create
-- create the client and store it in the global dictionary for the session
CREATE OR REPLACE FUNCTION ai.openai_client_create(
    _api_key text DEFAULT NULL,
    _api_key_name text DEFAULT NULL,
    _organization text DEFAULT NULL,
    _base_url text DEFAULT NULL,
    _timeout float8 DEFAULT NULL,
    _max_retries int DEFAULT NULL,
    _default_headers jsonb DEFAULT NULL,
    _default_query jsonb DEFAULT NULL,
    _http_client jsonb DEFAULT NULL,
    _strict_response_validation boolean DEFAULT NULL
) RETURNS void AS $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai

    if 'openai_client' not in GD:
        GD['openai_client'] = {}

    new_config = ai.openai.prepare_kwargs({
        'api_key': _api_key,
        'api_key_name': _api_key_name,
        'organization': _organization,
        'base_url': _base_url,
        'timeout': _timeout,
        'max_retries': _max_retries,
        'default_headers': ai.openai.process_json_input(_default_headers),
        'default_query': ai.openai.process_json_input(_default_query),
        'http_client': ai.openai.process_json_input(_http_client),
        '_strict_response_validation': _strict_response_validation
    })

    if 'config' not in GD['openai_client'] or ai.openai.client_config_changed(GD['openai_client']['config'], new_config):
        client = ai.openai.make_async_client(plpy, **new_config)
        GD['openai_client'] = {
            'client': client,
            'config': new_config
        }

$python$ LANGUAGE plpython3u VOLATILE SECURITY DEFINER PARALLEL UNSAFE;

-------------------------------------------------------------------------------
-- openai_client_destroy
-- remove the client object stored in the global dictionary for the session
CREATE OR REPLACE FUNCTION ai.openai_client_destroy() RETURNS void AS $python$
    #ADD-PYTHON-LIB-DIR
    if 'openai_client' in GD:
        del GD['openai_client']
$python$ LANGUAGE plpython3u VOLATILE SECURITY DEFINER PARALLEL UNSAFE;

-------------------------------------------------------------------------------
-- openai_list_models
-- list models supported on the openai platform
-- https://platform.openai.com/docs/api-reference/models/list
create or replace function ai.openai_list_models(
    _api_key text DEFAULT NULL,
    _api_key_name text DEFAULT NULL,
    _base_url text DEFAULT NULL,
    _extra_headers jsonb DEFAULT NULL,
    _extra_query jsonb DEFAULT NULL,
    _extra_body jsonb DEFAULT NULL,
    _timeout float8 DEFAULT NULL
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    import json

    # Create async client
    client = ai.openai.get_or_create_client(plpy, GD, _api_key, _api_key_name, _base_url)

    # Prepare kwargs for the API call
    kwargs = {}
    # Add extra parameters if provided
    if _extra_headers is not None:
        kwargs['extra_headers'] = json.loads(_extra_headers)
    if _extra_query is not None:
        kwargs['extra_query'] = json.loads(_extra_query)
    if _extra_body is not None:
        kwargs['extra_body'] = json.loads(_extra_body)

    async def async_openai_call(client, kwargs):
        response = await client.models.with_raw_response.list(**kwargs)
        return response.text

    # Execute the API call with cancellation support
    result = ai.openai.execute_with_cancellation(plpy, client, async_openai_call, **kwargs)

    return result
$python$
    language plpython3u volatile parallel unsafe security invoker
                        set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed
-- generate an embedding from a text value
-- https://platform.openai.com/docs/api-reference/embeddings/create
create or replace function ai.openai_embed
( _input text
, _model text
, _api_key text DEFAULT NULL
, _api_key_name text DEFAULT NULL
, _base_url text DEFAULT NULL
, _encoding_format text DEFAULT NULL
, _dimensions int DEFAULT NULL
, _user text DEFAULT NULL
, _extra_headers jsonb DEFAULT NULL
, _extra_query jsonb DEFAULT NULL
, _extra_body jsonb DEFAULT NULL
, _timeout float8 DEFAULT NULL
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    import json

    # Create async client
    client = ai.openai.get_or_create_client(plpy, GD, _api_key, _api_key_name, _base_url)

    # Prepare kwargs for the API call
    kwargs = ai.openai.prepare_kwargs({
        "input": [_input],
        "model": _model,
        "encoding_format": _encoding_format,
        "dimensions": _dimensions,
        "user": _user,
    })

    # Add extra parameters if provided
    if _extra_headers is not None:
        kwargs['extra_headers'] = json.loads(_extra_headers)
    if _extra_query is not None:
        kwargs['extra_query'] = json.loads(_extra_query)
    if _extra_body is not None:
        kwargs['extra_body'] = json.loads(_extra_body)

    async def async_openai_call(client, kwargs):
        response = await client.embeddings.with_raw_response.create(**kwargs)
        return response.text

    # Execute the API call with cancellation support
    result = ai.openai.execute_with_cancellation(plpy, client, async_openai_call, **kwargs)

    return result
$python$
    language plpython3u volatile parallel unsafe security invoker
                        set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed
-- generate embeddings from an array of text values
-- https://platform.openai.com/docs/api-reference/embeddings/create
create or replace function ai.openai_embed
( _input text[]
, _model text
, _api_key text DEFAULT NULL
, _api_key_name text DEFAULT NULL
, _base_url text DEFAULT NULL
, _encoding_format text DEFAULT NULL
, _dimensions int DEFAULT NULL
, _user text DEFAULT NULL
, _extra_headers jsonb DEFAULT NULL
, _extra_query jsonb DEFAULT NULL
, _extra_body jsonb DEFAULT NULL
, _timeout float8 DEFAULT NULL
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    import json

    # Create async client
    client = ai.openai.get_or_create_client(plpy, GD, _api_key, _api_key_name, _base_url)

    # Prepare kwargs for the API call
    kwargs = ai.openai.prepare_kwargs({
        "input": _input,
        "model": _model,
        "encoding_format": _encoding_format,
        "dimensions": _dimensions,
        "user": _user,
    })

    # Add extra parameters if provided
    if _extra_headers is not None:
        kwargs['extra_headers'] = json.loads(_extra_headers)
    if _extra_query is not None:
        kwargs['extra_query'] = json.loads(_extra_query)
    if _extra_body is not None:
        kwargs['extra_body'] = json.loads(_extra_body)

    async def async_openai_call(client, kwargs):
        response = await client.embeddings.with_raw_response.create(**kwargs)
        return response.text

    # Execute the API call with cancellation support
    result = ai.openai.execute_with_cancellation(plpy, client, async_openai_call, **kwargs)

    return result
$python$
    language plpython3u volatile parallel unsafe security invoker
                        set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed
-- generate embeddings from an array of tokens
-- https://platform.openai.com/docs/api-reference/embeddings/create
create or replace function ai.openai_embed
( _model text
, _input int[]
, _api_key text DEFAULT NULL
, _api_key_name text DEFAULT NULL
, _base_url text DEFAULT NULL
, _encoding_format text DEFAULT NULL
, _dimensions int DEFAULT NULL
, _user text DEFAULT NULL
, _extra_headers jsonb DEFAULT NULL
, _extra_query jsonb DEFAULT NULL
, _extra_body jsonb DEFAULT NULL
, _timeout float8 DEFAULT NULL
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    import json

    # Create async client
    client = ai.openai.get_or_create_client(plpy, GD, _api_key, _api_key_name, _base_url)

    # Prepare kwargs for the API call
    kwargs = ai.openai.prepare_kwargs({
        "input": [_input],
        "model": _model,
        "encoding_format": _encoding_format,
        "dimensions": _dimensions,
        "user": _user,
    })

    # Add extra parameters if provided
    if _extra_headers is not None:
        kwargs['extra_headers'] = json.loads(_extra_headers)
    if _extra_query is not None:
        kwargs['extra_query'] = json.loads(_extra_query)
    if _extra_body is not None:
        kwargs['extra_body'] = json.loads(_extra_body)

    async def async_openai_call(client, kwargs):
        response = await client.embeddings.with_raw_response.create(**kwargs)
        return response.text

    # Execute the API call with cancellation support
    result = ai.openai.execute_with_cancellation(plpy, client, async_openai_call, **kwargs)

    return result
$python$
    language plpython3u volatile parallel unsafe security invoker
                        set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_chat_complete
-- text generation / chat completion
-- https://platform.openai.com/docs/api-reference/chat/create
CREATE OR REPLACE FUNCTION ai.openai_chat_complete
( _messages jsonb
, _model text
, _api_key text DEFAULT NULL
, _api_key_name text DEFAULT NULL
, _base_url text DEFAULT NULL
, _frequency_penalty float8 DEFAULT NULL
, _logit_bias jsonb DEFAULT NULL
, _logprobs boolean DEFAULT NULL
, _top_logprobs int DEFAULT NULL
, _max_tokens int DEFAULT NULL
, _max_completion_tokens int DEFAULT NULL
, _n int DEFAULT NULL
, _presence_penalty float8 DEFAULT NULL
, _response_format jsonb DEFAULT NULL
, _seed int DEFAULT NULL
, _stop text DEFAULT NULL
, _stream boolean DEFAULT NULL
, _temperature float8 DEFAULT NULL
, _top_p float8 DEFAULT NULL
, _tools jsonb DEFAULT NULL
, _tool_choice jsonb DEFAULT NULL
, _user text DEFAULT NULL
, _metadata jsonb DEFAULT NULL
, _service_tier text DEFAULT NULL
, _store boolean DEFAULT NULL
, _parallel_tool_calls boolean DEFAULT NULL
, _extra_headers jsonb DEFAULT NULL
, _extra_query jsonb DEFAULT NULL
, _extra_body jsonb DEFAULT NULL
, _timeout float8 DEFAULT NULL
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    import json

    # Process JSON inputs
    messages = json.loads(_messages)
    if not isinstance(messages, list):
        plpy.error("_messages is not an array")

    # Handle _stream parameter since we cannot support it
    stream = False if _stream is None else _stream
    if stream:
        plpy.error("Streaming is not supported in this implementation")

    # Create async client
    client = ai.openai.get_or_create_client(plpy, GD, _api_key, _api_key_name, _base_url)

    # Prepare kwargs for the API call
    kwargs = ai.openai.prepare_kwargs({
        "model": _model,
        "messages": messages,
        "frequency_penalty": _frequency_penalty,
        "logit_bias": ai.openai.process_json_input(_logit_bias),
        "logprobs": _logprobs,
        "top_logprobs": _top_logprobs,
        "max_tokens": _max_tokens,
        "max_completion_tokens": _max_completion_tokens,
        "n": _n,
        "presence_penalty": _presence_penalty,
        "response_format": ai.openai.process_json_input(_response_format),
        "seed": _seed,
        "stop": _stop,
        "temperature": _temperature,
        "top_p": _top_p,
        "tools": ai.openai.process_json_input(_tools),
        "tool_choice": ai.openai.process_json_input(_tool_choice),
        "user": _user,
        "metadata": ai.openai.process_json_input(_metadata),
        "service_tier": _service_tier,
        "store": _store,
        "parallel_tool_calls": _parallel_tool_calls,
        "timeout": _timeout,
    })

    # Add extra parameters if provided
    if _extra_headers is not None:
        kwargs['extra_headers'] = json.loads(_extra_headers)
    if _extra_query is not None:
        kwargs['extra_query'] = json.loads(_extra_query)
    if _extra_body is not None:
        kwargs['extra_body'] = json.loads(_extra_body)

    async def async_openai_call(client, kwargs):
        response = await client.chat.completions.with_raw_response.create(**kwargs)
        return response.text

    # Execute the API call with cancellation support
    result = ai.openai.execute_with_cancellation(plpy, client, async_openai_call, **kwargs)

    return result
$python$
    LANGUAGE plpython3u volatile parallel unsafe security invoker
                        SET search_path TO pg_catalog, pg_temp
;

------------------------------------------------------------------------------------
-- openai_chat_complete_simple
-- simple chat completion that only requires a message and only returns the response
create or replace function ai.openai_chat_complete_simple
( _message text
, _api_key text DEFAULT NULL
, _api_key_name text DEFAULT NULL
) returns text
as $$
declare
    model text := 'gpt-4o';
    messages jsonb;
begin
    messages := pg_catalog.jsonb_build_array(
        pg_catalog.jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant'),
        pg_catalog.jsonb_build_object('role', 'user', 'content', _message)
    );
    return ai.openai_chat_complete(model, messages, _api_key)
        operator(pg_catalog.->)'choices'
        operator(pg_catalog.->)0
        operator(pg_catalog.->)'message'
        operator(pg_catalog.->>)'content';
end;
$$ language plpgsql volatile parallel unsafe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_moderate
-- classify text as potentially harmful or not
-- https://platform.openai.com/docs/api-reference/moderations/create
create or replace function ai.openai_moderate
(   _input text,
    _api_key text DEFAULT NULL,
    _api_key_name text DEFAULT NULL,
    _base_url text DEFAULT NULL,
    _model text DEFAULT NULL,
    _extra_headers jsonb DEFAULT NULL,
    _extra_query jsonb DEFAULT NULL,
    _extra_body jsonb DEFAULT NULL,
    _timeout float8 DEFAULT NULL
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    import json

    # Create async client
    client = ai.openai.get_or_create_client(plpy, GD, _api_key, _api_key_name, _base_url)

    # Prepare kwargs for the API call
    kwargs = ai.openai.prepare_kwargs({
        "model": _model,
        "input": _input,
    })

    # Add extra parameters if provided
    if _extra_headers is not None:
        kwargs['extra_headers'] = json.loads(_extra_headers)
    if _extra_query is not None:
        kwargs['extra_query'] = json.loads(_extra_query)
    if _extra_body is not None:
        kwargs['extra_body'] = json.loads(_extra_body)

    async def async_openai_call(client, kwargs):
        response = await client.moderations.with_raw_response.create(**kwargs)
        return response.text

    # Execute the API call with cancellation support
    result = ai.openai.execute_with_cancellation(plpy, client, async_openai_call, **kwargs)

    return result
$python$
    language plpython3u volatile parallel unsafe security invoker
                        set search_path to pg_catalog, pg_temp
;

create or replace function ai.openai_moderate
(   _input text[],
    _api_key text DEFAULT NULL,
    _api_key_name text DEFAULT NULL,
    _base_url text DEFAULT NULL,
    _model text DEFAULT NULL,
    _extra_headers jsonb DEFAULT NULL,
    _extra_query jsonb DEFAULT NULL,
    _extra_body jsonb DEFAULT NULL,
    _timeout float8 DEFAULT NULL
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    import json

    # Create async client
    client = ai.openai.get_or_create_client(plpy, GD, _api_key, _api_key_name, _base_url)

    # Prepare kwargs for the API call
    kwargs = ai.openai.prepare_kwargs({
        "model": _model,
        "input": _input,
    })

    # Add extra parameters if provided
    if _extra_headers is not None:
        kwargs['extra_headers'] = json.loads(_extra_headers)
    if _extra_query is not None:
        kwargs['extra_query'] = json.loads(_extra_query)
    if _extra_body is not None:
        kwargs['extra_body'] = json.loads(_extra_body)

    async def async_openai_call(client, kwargs):
        response = await client.moderations.with_raw_response.create(**kwargs)
        return response.text

    # Execute the API call with cancellation support
    result = ai.openai.execute_with_cancellation(plpy, client, async_openai_call, **kwargs)

    return result
$python$
    language plpython3u volatile parallel unsafe security invoker
                        set search_path to pg_catalog, pg_temp
;
