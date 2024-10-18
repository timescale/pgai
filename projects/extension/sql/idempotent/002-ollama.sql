
-------------------------------------------------------------------------------
-- ollama_list_models
-- https://github.com/ollama/ollama/blob/main/docs/api.md#list-local-models
--
create or replace function ai.ollama_list_models(_host text default null)
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
    client = ai.ollama.make_client(plpy, _host)
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
create or replace function ai.ollama_ps(_host text default null)
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
    client = ai.ollama.make_client(plpy, _host)
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
( _model text
, _input text
, _host text default null
, _keep_alive float8 default null
, _options jsonb default null
) returns @extschema:vector@.vector
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.ollama
    client = ai.ollama.make_client(plpy, _host)
    _options_1 = None
    if _options is not None:
        import json
        _options_1 = {k: v for k, v in json.loads(_options).items()}
    resp = client.embeddings(_model, _input, options=_options, keep_alive=_keep_alive)
    return resp.get("embedding")
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- ollama_generate
-- https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-completion
create or replace function ai.ollama_generate
( _model text
, _prompt text
, _host text default null
, _images bytea[] default null
, _keep_alive float8 default null
, _options jsonb default null
, _system text default null
, _template text default null
, _context int[] default null
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.ollama
    client = ai.ollama.make_client(plpy, _host)

    import json
    args = {}

    if _keep_alive is not None:
        args["keep_alive"] = _keep_alive

    if _options is not None:
        args["options"] = {k: v for k, v in json.loads(_options).items()}

    if _system is not None:
        args["system"] = _system

    if _template is not None:
        args["template"] = _template

    if _context is not None:
        args["context"] = _context

    _images_1 = None
    if _images is not None:
        import base64
        _images_1 = []
        for image in _images:
            _images_1.append(base64.b64encode(image).decode('utf-8'))
        args["images"] = _images_1

    resp = client.generate(_model, _prompt, stream=False, **args)
    return json.dumps(resp)
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- ollama_chat_complete
-- https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-chat-completion
create or replace function ai.ollama_chat_complete
( _model text
, _messages jsonb
, _host text default null
, _keep_alive float8 default null
, _options jsonb default null
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.ollama
    client = ai.ollama.make_client(plpy, _host)

    import json
    import base64
    args = {}

    if _keep_alive is not None:
        args["keep_alive"] = _keep_alive

    if _options is not None:
        args["options"] = {k: v for k, v in json.loads(_options).items()}

    _messages_1 = json.loads(_messages)
    if not isinstance(_messages_1, list):
        plpy.error("_messages is not an array")

    # the python api expects bytes objects for images
    # decode the base64 encoded images into raw binary
    for message in _messages_1:
        if 'images' in message:
            decoded = [base64.b64decode(image) for image in message["images"]]
            message["images"] = decoded

    resp = client.chat(_model, _messages_1, stream=False, **args)

    return json.dumps(resp)
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;
