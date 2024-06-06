-------------------------------------------------------------------------------
-- ai 0.1.0

-------------------------------------------------------------------------------
-- openai_tokenize
-- encode text as tokens for a given model
-- https://github.com/openai/tiktoken/blob/main/README.md
create function @extschema@.openai_tokenize(_model text, _text text) returns int[]
as $func$
import tiktoken
encoding = tiktoken.encoding_for_model(_model)
tokens = encoding.encode(_text)
return tokens
$func$
language plpython3u strict volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_detokenize
-- decode tokens for a given model back into text
-- https://github.com/openai/tiktoken/blob/main/README.md
create function @extschema@.openai_detokenize(_model text, _tokens int[]) returns text
as $func$
import tiktoken
encoding = tiktoken.encoding_for_model(_model)
content = encoding.decode(_tokens)
return content
$func$
language plpython3u strict volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_list_models
-- list models supported on the openai platform
-- https://platform.openai.com/docs/api-reference/models/list
create function @extschema@.openai_list_models(_api_key text default null)
returns table
( id text
, created timestamptz
, owned_by text
)
as $func$
_api_key_1 = _api_key
if _api_key_1 is None:
    r = plpy.execute("select pg_catalog.current_setting('ai.openai_api_key', true) as api_key")
    if len(r) >= 0:
        _api_key_1 = r[0]["api_key"]
if _api_key_1 is None:
    plpy.error("missing api key")
import openai
client = openai.OpenAI(api_key=_api_key_1)
from datetime import datetime, timezone
for model in client.models.list():
    created = datetime.fromtimestamp(model.created, timezone.utc)
    yield (model.id, created, model.owned_by)
$func$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed
-- generate an embedding from a text value
-- https://platform.openai.com/docs/api-reference/embeddings/create
create function @extschema@.openai_embed
( _model text
, _input text
, _api_key text default null
, _dimensions int default null
, _user text default null
) returns vector
as $func$
_api_key_1 = _api_key
if _api_key_1 is None:
    r = plpy.execute("select pg_catalog.current_setting('ai.openai_api_key', true) as api_key")
    if len(r) >= 0:
        _api_key_1 = r[0]["api_key"]
if _api_key_1 is None:
    plpy.error("missing api key")
import openai
client = openai.OpenAI(api_key=_api_key_1)
args = {}
if _dimensions is not None:
  args["dimensions"] = _dimensions
if _user is not None:
  args["user"] = _user
response = client.embeddings.create(input=[_input], model=_model, **args)
if not hasattr(response, "data") or len(response.data) == 0:
  return null
return response.data[0].embedding
$func$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed
-- generate embeddings from an array of text values
-- https://platform.openai.com/docs/api-reference/embeddings/create
create function @extschema@.openai_embed
( _model text
, _input text[]
, _api_key text default null
, _dimensions int default null
, _user text default null
) returns table
( "index" int
, embedding @extschema:vector@.vector
)
as $func$
_api_key_1 = _api_key
if _api_key_1 is None:
    r = plpy.execute("select pg_catalog.current_setting('ai.openai_api_key', true) as api_key")
    if len(r) >= 0:
        _api_key_1 = r[0]["api_key"]
if _api_key_1 is None:
    plpy.error("missing api key")
import openai
client = openai.OpenAI(api_key=_api_key_1)
args = {}
if _dimensions is not None:
  args["dimensions"] = _dimensions
if _user is not None:
  args["user"] = _user
response = client.embeddings.create(input=_input, model=_model, **args)
for obj in response.data:
    yield (obj.index, obj.embedding)
$func$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed
-- generate embeddings from an array of tokens
-- https://platform.openai.com/docs/api-reference/embeddings/create
create function @extschema@.openai_embed
( _model text
, _input int[]
, _api_key text default null
, _dimensions int default null
, _user text default null
) returns @extschema:vector@.vector
as $func$
_api_key_1 = _api_key
if _api_key_1 is None:
    r = plpy.execute("select pg_catalog.current_setting('ai.openai_api_key', true) as api_key")
    if len(r) >= 0:
        _api_key_1 = r[0]["api_key"]
if _api_key_1 is None:
    plpy.error("missing api key")
import openai
client = openai.OpenAI(api_key=_api_key_1)
args = {}
if _dimensions is not None:
  args["dimensions"] = _dimensions
if _user is not None:
  args["user"] = _user
response = client.embeddings.create(input=[_input], model=_model, **args)
if not hasattr(response, "data") or len(response.data) == 0:
  return null
return response.data[0].embedding
$func$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_chat_complete
-- text generation / chat completion
-- https://platform.openai.com/docs/api-reference/chat/create
create function @extschema@.openai_chat_complete
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
as $func$
_api_key_1 = _api_key
if _api_key_1 is None:
    r = plpy.execute("select pg_catalog.current_setting('ai.openai_api_key', true) as api_key")
    if len(r) >= 0:
        _api_key_1 = r[0]["api_key"]
if _api_key_1 is None:
    plpy.error("missing api key")
import openai
client = openai.OpenAI(api_key=_api_key_1)
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
$func$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_moderate
-- classify text as potentially harmful or not
-- https://platform.openai.com/docs/api-reference/moderations/create
create function @extschema@.openai_moderate
( _model text
, _input text
, _api_key text default null
) returns jsonb
as $func$
_api_key_1 = _api_key
if _api_key_1 is None:
    r = plpy.execute("select pg_catalog.current_setting('ai.openai_api_key', true) as api_key")
    if len(r) >= 0:
        _api_key_1 = r[0]["api_key"]
if _api_key_1 is None:
    plpy.error("missing api key")
import openai
client = openai.OpenAI(api_key=_api_key_1)
moderation = client.moderations.create(input=_input, model=_model)
return moderation.model_dump_json()
$func$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;
