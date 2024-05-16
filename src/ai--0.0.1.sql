
create function openai_tokenize(_model text, _text text) returns int[]
as $func$
import tiktoken
encoding = tiktoken.encoding_for_model(_model)
tokens = encoding.encode(_text)
return tokens
$func$ 
language plpython3u strict volatile parallel safe security definer
set search_path to pg_catalog, pg_temp
;

create function openai_list_models(_api_key text) returns table
( id text
, created timestamptz
, owned_by text
)
as $func$
import openai
from datetime import datetime, timezone
client = openai.OpenAI(api_key=_api_key)
for model in client.models.list():
    created = datetime.fromtimestamp(model.created, timezone.utc)
    yield (model.id, created, model.owned_by)
$func$ 
language plpython3u strict volatile parallel safe security definer
set search_path to pg_catalog, pg_temp
;

create function openai_embed(_model text, _api_key text, _text text) returns vector
as $func$
import openai
client = openai.OpenAI(api_key=_api_key)
response = client.embeddings.create(input = [_text], model=_model)
return response.data[0].embedding
$func$ 
language plpython3u strict volatile parallel safe security definer
set search_path to pg_catalog, pg_temp
;

create function openai_embed(_model text, _api_key text, _texts text[]) returns setof vector
as $func$
import openai
client = openai.OpenAI(api_key=_api_key)
response = client.embeddings.create(input = _texts, model=_model)
for obj in response.data:
    yield obj.embedding
$func$ 
language plpython3u strict volatile parallel safe security definer
set search_path to pg_catalog, pg_temp
;

create function openai_chat_complete
( _model text
, _api_key text
, _messages jsonb
, _frequency_penalty float8 default null
, _max_tokens int default null
, _n int default null
, _response_format jsonb default null
, _seed int default null
, _temperature float8 default null
, _top_p float8 default null
, _user text default null
) returns jsonb
as $func$
import openai
import json
client = openai.OpenAI(api_key=_api_key)

rf = None
if _response_format is not None:
    rf = json.loads(_response_format)
    rf = {'type': rf['type']}
    if rf['type'] not in {'text', 'json_object'}:
        plpy.error("invalid response format.",
            hint = "use {'type': 'text'} or {'type': 'json_object'}")

msgs = json.loads(_messages)
if not isinstance(msgs, list):
    plpy.error("_messages is not an array")

msgs = [{'role': msg['role'], 'content': msg['content']} for msg in msgs]

response = client.chat.completions.create(
  model=_model
, messages=msgs
, frequency_penalty=_frequency_penalty
, max_tokens=_max_tokens
, n=_n
, response_format=rf
, seed=_seed
, stream=False
, temperature=_temperature
, top_p=_top_p
, user=_user
)

completion = {
  "id": response.id,
  "object": "chat.completion",
  "created": response.created,
  "model": response.model,
  "system_fingerprint": response.system_fingerprint,
  "choices": [{
    "index": choice.index,
    "message": {
      "role": choice.message.role,
      "content": choice.message.content,
    },
    "logprobs": choice.logprobs,
    "finish_reason": choice.finish_reason
  } for choice in response.choices],
  "usage": {
    "prompt_tokens": response.usage.prompt_tokens,
    "completion_tokens": response.usage.completion_tokens,
    "total_tokens": response.usage.total_tokens
  }
}

return json.dumps(completion)
$func$ 
language plpython3u volatile parallel safe security definer
set search_path to pg_catalog, pg_temp
;
