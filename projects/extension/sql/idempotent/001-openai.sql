
-------------------------------------------------------------------------------
-- openai_tokenize
-- encode text as tokens for a given model
-- https://github.com/openai/tiktoken/blob/main/README.md
create or replace function ai.openai_tokenize(model text, text_input text) returns int[]
as $python$
    #ADD-PYTHON-LIB-DIR
    import tiktoken
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(text_input)
    return tokens
$python$
    language plpython3u strict immutable parallel safe security invoker
                        set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_detokenize
-- decode tokens for a given model back into text
-- https://github.com/openai/tiktoken/blob/main/README.md
create or replace function ai.openai_detokenize(model text, tokens int[]) returns text
as $python$
    #ADD-PYTHON-LIB-DIR
    import tiktoken
    encoding = tiktoken.encoding_for_model(model)
    content = encoding.decode(tokens)
    return content
$python$
    language plpython3u strict immutable parallel safe security invoker
                        set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_list_models
-- list models supported on the openai platform
-- https://platform.openai.com/docs/api-reference/models/list
create or replace function ai.openai_list_models(
    api_key text DEFAULT NULL,
    api_key_name text DEFAULT NULL,
    base_url text DEFAULT NULL,
    extra_headers jsonb DEFAULT NULL,
    extra_query jsonb DEFAULT NULL,
    extra_body jsonb DEFAULT NULL,
    timeout float8 DEFAULT NULL,
    client_extra_args jsonb DEFAULT NULL
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    import json

    # Prepare client args
    client_kwargs = ai.openai.process_json_input(client_extra_args) if client_extra_args is not None else {}
    # Create async client
    client = ai.openai.get_or_create_client(plpy, GD, api_key, api_key_name, base_url, **client_kwargs)

    # Prepare kwargs for the API call
    kwargs = {}
    # Add extra parameters if provided
    if extra_headers is not None:
        kwargs['extra_headers'] = json.loads(extra_headers)
    if extra_query is not None:
        kwargs['extra_query'] = json.loads(extra_query)
    if extra_body is not None:
        kwargs['extra_body'] = json.loads(extra_body)

    async def async_openai_call(client, kwargs):
        response = await client.models.with_raw_response.list(**kwargs)
        return response.text

    # Execute the API call with cancellation support
    result = ai.openai.execute_with_cancellation(plpy, client, async_openai_call, **kwargs)

    return result
$python$
    language plpython3u immutable parallel safe security invoker
                        set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed
-- generate an embedding from a text value
-- https://platform.openai.com/docs/api-reference/embeddings/create
create or replace function ai.openai_embed
( input text
, model text
, api_key text DEFAULT NULL
, api_key_name text DEFAULT NULL
, base_url text DEFAULT NULL
, encoding_format text DEFAULT NULL
, dimensions int DEFAULT NULL
, openai_user text DEFAULT NULL
, extra_headers jsonb DEFAULT NULL
, extra_query jsonb DEFAULT NULL
, extra_body jsonb DEFAULT NULL
, timeout float8 DEFAULT NULL
, client_extra_args jsonb DEFAULT NULL
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    import json

    # Prepare client args
    client_kwargs = ai.openai.process_json_input(client_extra_args) if client_extra_args is not None else {}
    # Create async client
    client = ai.openai.get_or_create_client(plpy, GD, api_key, api_key_name, base_url, **client_kwargs)

    # Prepare kwargs for the API call
    kwargs = ai.openai.prepare_kwargs({
        "input": [input],
        "model": model,
        "encoding_format": encoding_format,
        "dimensions": dimensions,
        "user": openai_user,
    })

    # Add extra parameters if provided
    if extra_headers is not None:
        kwargs['extra_headers'] = json.loads(extra_headers)
    if extra_query is not None:
        kwargs['extra_query'] = json.loads(extra_query)
    if extra_body is not None:
        kwargs['extra_body'] = json.loads(extra_body)

    async def async_openai_call(client, kwargs):
        response = await client.embeddings.with_raw_response.create(**kwargs)
        return response.text

    # Execute the API call with cancellation support
    result = ai.openai.execute_with_cancellation(plpy, client, async_openai_call, **kwargs)

    return result
$python$
    language plpython3u immutable parallel safe security invoker
                        set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed
-- generate embeddings from an array of text values
-- https://platform.openai.com/docs/api-reference/embeddings/create
create or replace function ai.openai_embed
( input text[]
, model text
, api_key text DEFAULT NULL
, api_key_name text DEFAULT NULL
, base_url text DEFAULT NULL
, encoding_format text DEFAULT NULL
, dimensions int DEFAULT NULL
, openai_user text DEFAULT NULL
, extra_headers jsonb DEFAULT NULL
, extra_query jsonb DEFAULT NULL
, extra_body jsonb DEFAULT NULL
, timeout float8 DEFAULT NULL
, client_extra_args jsonb DEFAULT NULL
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    import json

    # Prepare client args
    client_kwargs = ai.openai.process_json_input(client_extra_args) if client_extra_args is not None else {}
    # Create async client
    client = ai.openai.get_or_create_client(plpy, GD, api_key, api_key_name, base_url, **client_kwargs)

    # Prepare kwargs for the API call
    kwargs = ai.openai.prepare_kwargs({
        "input": input,
        "model": model,
        "encoding_format": encoding_format,
        "dimensions": dimensions,
        "user": openai_user,
    })

    # Add extra parameters if provided
    if extra_headers is not None:
        kwargs['extra_headers'] = json.loads(extra_headers)
    if extra_query is not None:
        kwargs['extra_query'] = json.loads(extra_query)
    if extra_body is not None:
        kwargs['extra_body'] = json.loads(extra_body)

    async def async_openai_call(client, kwargs):
        response = await client.embeddings.with_raw_response.create(**kwargs)
        return response.text

    # Execute the API call with cancellation support
    result = ai.openai.execute_with_cancellation(plpy, client, async_openai_call, **kwargs)

    return result
$python$
    language plpython3u immutable parallel safe security invoker
                        set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed
-- generate embeddings from an array of tokens
-- https://platform.openai.com/docs/api-reference/embeddings/create
create or replace function ai.openai_embed
( model text
, input int[]
, api_key text DEFAULT NULL
, api_key_name text DEFAULT NULL
, base_url text DEFAULT NULL
, encoding_format text DEFAULT NULL
, dimensions int DEFAULT NULL
, openai_user text DEFAULT NULL
, extra_headers jsonb DEFAULT NULL
, extra_query jsonb DEFAULT NULL
, extra_body jsonb DEFAULT NULL
, timeout float8 DEFAULT NULL
, client_extra_args jsonb DEFAULT NULL
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    import json

    # Prepare client args
    client_kwargs = ai.openai.process_json_input(client_extra_args) if client_extra_args is not None else {}
    # Create async client
    client = ai.openai.get_or_create_client(plpy, GD, api_key, api_key_name, base_url, **client_kwargs)

    # Prepare kwargs for the API call
    kwargs = ai.openai.prepare_kwargs({
        "input": [input],
        "model": model,
        "encoding_format": encoding_format,
        "dimensions": dimensions,
        "user": openai_user,
    })

    # Add extra parameters if provided
    if extra_headers is not None:
        kwargs['extra_headers'] = json.loads(extra_headers)
    if extra_query is not None:
        kwargs['extra_query'] = json.loads(extra_query)
    if extra_body is not None:
        kwargs['extra_body'] = json.loads(extra_body)

    async def async_openai_call(client, kwargs):
        response = await client.embeddings.with_raw_response.create(**kwargs)
        return response.text

    # Execute the API call with cancellation support
    result = ai.openai.execute_with_cancellation(plpy, client, async_openai_call, **kwargs)

    return result
$python$
    language plpython3u immutable parallel safe security invoker
                        set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_chat_complete
-- text generation / chat completion
-- https://platform.openai.com/docs/api-reference/chat/create
CREATE OR REPLACE FUNCTION ai.openai_chat_complete
( messages jsonb
, model text
, api_key text DEFAULT NULL
, api_key_name text DEFAULT NULL
, base_url text DEFAULT NULL
, frequency_penalty float8 DEFAULT NULL
, logit_bias jsonb DEFAULT NULL
, logprobs boolean DEFAULT NULL
, top_logprobs int DEFAULT NULL
, max_tokens int DEFAULT NULL
, max_completion_tokens int DEFAULT NULL
, n int DEFAULT NULL
, presence_penalty float8 DEFAULT NULL
, response_format jsonb DEFAULT NULL
, seed int DEFAULT NULL
, stop text DEFAULT NULL
, stream boolean DEFAULT NULL
, temperature float8 DEFAULT NULL
, top_p float8 DEFAULT NULL
, tools jsonb DEFAULT NULL
, tool_choice jsonb DEFAULT NULL
, openai_user text DEFAULT NULL
, metadata jsonb DEFAULT NULL
, service_tier text DEFAULT NULL
, store boolean DEFAULT NULL
, parallel_tool_calls boolean DEFAULT NULL
, extra_headers jsonb DEFAULT NULL
, extra_query jsonb DEFAULT NULL
, extra_body jsonb DEFAULT NULL
, timeout float8 DEFAULT NULL
, client_extra_args jsonb DEFAULT NULL
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    import json

    # Process JSON inputs
    messages_parsed = json.loads(messages)
    if not isinstance(messages_parsed, list):
        plpy.error("messages is not an array")

    # Handle stream parameter since we cannot support it
    stream_val = False if stream is None else stream
    if stream_val:
        plpy.error("Streaming is not supported in this implementation")

    # Prepare client args
    client_kwargs = ai.openai.process_json_input(client_extra_args) if client_extra_args is not None else {}
    # Create async client
    client = ai.openai.get_or_create_client(plpy, GD, api_key, api_key_name, base_url, **client_kwargs)

    # Prepare kwargs for the API call
    kwargs = ai.openai.prepare_kwargs({
        "model": model,
        "messages": messages_parsed,
        "frequency_penalty": frequency_penalty,
        "logit_bias": ai.openai.process_json_input(logit_bias),
        "logprobs": logprobs,
        "top_logprobs": top_logprobs,
        "max_tokens": max_tokens,
        "max_completion_tokens": max_completion_tokens,
        "n": n,
        "presence_penalty": presence_penalty,
        "response_format": ai.openai.process_json_input(response_format),
        "seed": seed,
        "stop": stop,
        "temperature": temperature,
        "top_p": top_p,
        "tools": ai.openai.process_json_input(tools),
        "tool_choice": ai.openai.process_json_input(tool_choice),
        "user": openai_user,
        "metadata": ai.openai.process_json_input(metadata),
        "service_tier": service_tier,
        "store": store,
        "parallel_tool_calls": parallel_tool_calls,
        "timeout": timeout,
    })

    # Add extra parameters if provided
    if extra_headers is not None:
        kwargs['extra_headers'] = json.loads(extra_headers)
    if extra_query is not None:
        kwargs['extra_query'] = json.loads(extra_query)
    if extra_body is not None:
        kwargs['extra_body'] = json.loads(extra_body)

    async def async_openai_call(client, kwargs):
        response = await client.chat.completions.with_raw_response.create(**kwargs)
        return response.text

    # Execute the API call with cancellation support
    result = ai.openai.execute_with_cancellation(plpy, client, async_openai_call, **kwargs)

    return result
$python$
    LANGUAGE plpython3u volatile parallel safe security invoker
                        SET search_path TO pg_catalog, pg_temp
;

------------------------------------------------------------------------------------
-- openai_chat_complete_simple
-- simple chat completion that only requires a message and only returns the response
create or replace function ai.openai_chat_complete_simple
( message text
, api_key text DEFAULT NULL
, api_key_name text DEFAULT NULL
) returns text
as $$
declare
    model text := 'gpt-4o';
    messages jsonb;
begin
    messages := pg_catalog.jsonb_build_array(
            pg_catalog.jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant'),
            pg_catalog.jsonb_build_object('role', 'user', 'content', message)
                );
    return ai.openai_chat_complete(model, messages, api_key, api_key_name)
               operator(pg_catalog.->)'choices'
               operator(pg_catalog.->)0
               operator(pg_catalog.->)'message'
        operator(pg_catalog.->>)'content';
end;
$$ language plpgsql volatile parallel safe security invoker
                    set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_moderate
-- classify text as potentially harmful or not
-- https://platform.openai.com/docs/api-reference/moderations/create
create or replace function ai.openai_moderate
(   input text,
    api_key text DEFAULT NULL,
    api_key_name text DEFAULT NULL,
    base_url text DEFAULT NULL,
    model text DEFAULT NULL,
    extra_headers jsonb DEFAULT NULL,
    extra_query jsonb DEFAULT NULL,
    extra_body jsonb DEFAULT NULL,
    timeout float8 DEFAULT NULL,
    client_extra_args jsonb DEFAULT NULL
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    import json

    # Prepare client args
    client_kwargs = ai.openai.process_json_input(client_extra_args) if client_extra_args is not None else {}
    # Create async client
    client = ai.openai.get_or_create_client(plpy, GD, api_key, api_key_name, base_url, **client_kwargs)

    # Prepare kwargs for the API call
    kwargs = ai.openai.prepare_kwargs({
        "model": model,
        "input": input,
    })

    # Add extra parameters if provided
    if extra_headers is not None:
        kwargs['extra_headers'] = json.loads(extra_headers)
    if extra_query is not None:
        kwargs['extra_query'] = json.loads(extra_query)
    if extra_body is not None:
        kwargs['extra_body'] = json.loads(extra_body)

    async def async_openai_call(client, kwargs):
        response = await client.moderations.with_raw_response.create(**kwargs)
        return response.text

    # Execute the API call with cancellation support
    result = ai.openai.execute_with_cancellation(plpy, client, async_openai_call, **kwargs)

    return result
$python$
    language plpython3u stable parallel safe security invoker
                        set search_path to pg_catalog, pg_temp
;

create or replace function ai.openai_moderate
(   input text[],
    api_key text DEFAULT NULL,
    api_key_name text DEFAULT NULL,
    base_url text DEFAULT NULL,
    model text DEFAULT NULL,
    extra_headers jsonb DEFAULT NULL,
    extra_query jsonb DEFAULT NULL,
    extra_body jsonb DEFAULT NULL,
    timeout float8 DEFAULT NULL,
    client_extra_args jsonb DEFAULT NULL
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    import json

    # Prepare client args
    client_kwargs = ai.openai.process_json_input(client_extra_args) if client_extra_args is not None else {}
    # Create async client
    client = ai.openai.get_or_create_client(plpy, GD, api_key, api_key_name, base_url, **client_kwargs)

    # Prepare kwargs for the API call
    kwargs = ai.openai.prepare_kwargs({
        "model": model,
        "input": input,
    })

    # Add extra parameters if provided
    if extra_headers is not None:
        kwargs['extra_headers'] = json.loads(extra_headers)
    if extra_query is not None:
        kwargs['extra_query'] = json.loads(extra_query)
    if extra_body is not None:
        kwargs['extra_body'] = json.loads(extra_body)

    async def async_openai_call(client, kwargs):
        response = await client.moderations.with_raw_response.create(**kwargs)
        return response.text

    # Execute the API call with cancellation support
    result = ai.openai.execute_with_cancellation(plpy, client, async_openai_call, **kwargs)

    return result
$python$
    language plpython3u stable parallel unsafe security invoker
                        set search_path to pg_catalog, pg_temp
;
