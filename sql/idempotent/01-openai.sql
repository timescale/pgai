
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
language plpython3u strict volatile parallel safe security invoker
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
language plpython3u strict volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_list_models
-- list models supported on the openai platform
-- https://platform.openai.com/docs/api-reference/models/list
create or replace function ai.openai_list_models(_api_key text default null)
returns table
( id text
, created timestamptz
, owned_by text
)
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    for tup in ai.openai.list_models(plpy, _api_key):
        yield tup
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed
-- generate an embedding from a text value
-- https://platform.openai.com/docs/api-reference/embeddings/create
create or replace function ai.openai_embed
( _model text
, _input text
, _api_key text default null
, _dimensions int default null
, _user text default null
) returns @extschema:vector@.vector
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    for tup in ai.openai.embed(plpy, _model, _input, api_key=_api_key, dimensions=_dimensions, user=_user):
        return tup[1]
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed
-- generate embeddings from an array of text values
-- https://platform.openai.com/docs/api-reference/embeddings/create
create or replace function ai.openai_embed
( _model text
, _input text[]
, _api_key text default null
, _dimensions int default null
, _user text default null
) returns table
( "index" int
, embedding @extschema:vector@.vector
)
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    for tup in ai.openai.embed(plpy, _model, _input, api_key=_api_key, dimensions=_dimensions, user=_user):
        yield tup
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed
-- generate embeddings from an array of tokens
-- https://platform.openai.com/docs/api-reference/embeddings/create
create or replace function ai.openai_embed
( _model text
, _input int[]
, _api_key text default null
, _dimensions int default null
, _user text default null
) returns @extschema:vector@.vector
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    for tup in ai.openai.embed(plpy, _model, _input, api_key=_api_key, dimensions=_dimensions, user=_user):
        return tup[1]
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_chat_complete
-- text generation / chat completion
-- https://platform.openai.com/docs/api-reference/chat/create
create or replace function ai.openai_chat_complete
( _model text
, _messages jsonb
, _api_key text default null
, _frequency_penalty float8 default null
, _logit_bias jsonb default null
, _logprobs boolean default null
, _top_logprobs int default null
, _max_tokens int default null
, _n int default null
, _presence_penalty float8 default null
, _response_format jsonb default null
, _seed int default null
, _stop text default null
, _temperature float8 default null
, _top_p float8 default null
, _tools jsonb default null
, _tool_choice jsonb default null
, _user text default null
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    client = ai.openai.make_client(plpy, _api_key)
    import json

    _messages_1 = json.loads(_messages)
    if not isinstance(_messages_1, list):
        plpy.error("_messages is not an array")

    _logit_bias_1 = None
    if _logit_bias is not None:
      _logit_bias_1 = json.loads(_logit_bias)

    _response_format_1 = None
    if _response_format is not None:
      _response_format_1 = json.loads(_response_format)

    _tools_1 = None
    if _tools is not None:
      _tools_1 = json.loads(_tools)

    _tool_choice_1 = None
    if _tool_choice is not None:
      _tool_choice_1 = json.loads(_tool_choice)

    response = client.chat.completions.create(
      model=_model
    , messages=_messages_1
    , frequency_penalty=_frequency_penalty
    , logit_bias=_logit_bias_1
    , logprobs=_logprobs
    , top_logprobs=_top_logprobs
    , max_tokens=_max_tokens
    , n=_n
    , presence_penalty=_presence_penalty
    , response_format=_response_format_1
    , seed=_seed
    , stop=_stop
    , stream=False
    , temperature=_temperature
    , top_p=_top_p
    , tools=_tools_1
    , tool_choice=_tool_choice_1
    , user=_user
    )

    return response.model_dump_json()
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_moderate
-- classify text as potentially harmful or not
-- https://platform.openai.com/docs/api-reference/moderations/create
create or replace function ai.openai_moderate
( _model text
, _input text
, _api_key text default null
) returns jsonb
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.openai
    client = ai.openai.make_client(plpy, _api_key)
    moderation = client.moderations.create(input=_input, model=_model)
    return moderation.model_dump_json()
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;
