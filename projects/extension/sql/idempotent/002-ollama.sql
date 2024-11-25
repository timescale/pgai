
-------------------------------------------------------------------------------
-- ollama_list_models
-- https://github.com/ollama/ollama/blob/main/docs/api.md#list-local-models
--
create or replace function ai.ollama_list_models(host text default null)
returns table
( "name" text
, model text
, size bigint
, digest text
, family text
, format text
, families jsonb
, parent_model text
, parameter_size text
, quantization_level text
, modified_at timestamptz
)
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.ollama
    client = ai.ollama.make_client(plpy, host)
    import json
    resp = client.list()
    models = resp.get("models")
    if models is None:
        raise StopIteration
    for m in models:
        d = m.get("details")
        yield ( m.get("name")
            , m.get("model")
            , m.get("size")
            , m.get("digest")
            , d.get("family") if d is not None else None
            , d.get("format") if d is not None else None
            , json.dumps(d.get("families")) if d is not None else None
            , d.get("parent_model") if d is not None else None
            , d.get("parameter_size") if d is not None else None
            , d.get("quantization_level") if d is not None else None
            , m.get("modified_at")
        )
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- ollama_ps
-- https://github.com/ollama/ollama/blob/main/docs/api.md#list-running-models
create or replace function ai.ollama_ps(host text default null)
returns table
( "name" text
, model text
, size bigint
, digest text
, parent_model text
, format text
, family text
, families jsonb
, parameter_size text
, quantization_level text
, expires_at timestamptz
, size_vram bigint
)
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.ollama
    client = ai.ollama.make_client(plpy, host)
    import json
    resp = client.ps()
    models = resp.get("models")
    if models is None:
        raise StopIteration
    for m in models:
        d = m.get("details")
        yield ( m.get("name")
            , m.get("model")
            , m.get("size")
            , m.get("digest")
            , d.get("parent_model") if d is not None else None
            , d.get("format") if d is not None else None
            , d.get("family") if d is not None else None
            , json.dumps(d.get("families")) if d is not None else None
            , d.get("parameter_size") if d is not None else None
            , d.get("quantization_level") if d is not None else None
            , m.get("expires_at")
            , m.get("size_vram")
        )
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- ollama_embed
-- https://github.com/ollama/ollama/blob/main/docs/api.md#generate-embeddings
create or replace function ai.ollama_embed
( model text
, input_text text
, host text default null
, keep_alive text default null
, embedding_options jsonb default null
) returns @extschema:vector@.vector
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.ollama
    client = ai.ollama.make_client(plpy, host)
    embedding_options_1 = None
    if embedding_options is not None:
        import json
        embedding_options_1 = {k: v for k, v in json.loads(embedding_options).items()}
    resp = client.embeddings(model, input_text, options=embedding_options_1, keep_alive=keep_alive)
    return resp.get("embedding")
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- ollama_generate
-- https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-completion
create or replace function ai.ollama_generate
( model text
, prompt text
, host text default null
, images bytea[] default null
, keep_alive text default null
, embedding_options jsonb default null
, system_prompt text default null
, template text default null
, context int[] default null
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.ollama
    client = ai.ollama.make_client(plpy, host)

    import json
    args = {}

    if keep_alive is not None:
        args["keep_alive"] = keep_alive

    if embedding_options is not None:
        args["options"] = {k: v for k, v in json.loads(embedding_options).items()}

    if system_prompt is not None:
        args["system"] = system_prompt

    if template is not None:
        args["template"] = template

    if context is not None:
        args["context"] = context

    if images is not None:
        import base64
        images_1 = []
        for image in images:
            images_1.append(base64.b64encode(image).decode('utf-8'))
        args["images"] = images_1

    resp = client.generate(model, prompt, stream=False, **args)
    return json.dumps(resp)
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- ollama_chat_complete
-- https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-chat-completion
create or replace function ai.ollama_chat_complete
( model text
, messages jsonb
, host text default null
, keep_alive text default null
, chat_options jsonb default null
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.ollama
    client = ai.ollama.make_client(plpy, host)

    import json
    import base64
    args = {}

    if keep_alive is not None:
        args["keep_alive"] = keep_alive

    if chat_options is not None:
        args["options"] = {k: v for k, v in json.loads(chat_options).items()}

    messages_1 = json.loads(messages)
    if not isinstance(messages_1, list):
        plpy.error("messages is not an array")

    # the python api expects bytes objects for images
    # decode the base64 encoded images into raw binary
    for message in messages_1:
        if 'images' in message:
            decoded = [base64.b64decode(image) for image in message["images"]]
            message["images"] = decoded

    resp = client.chat(model, messages_1, stream=False, **args)

    return json.dumps(resp)
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;
