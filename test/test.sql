-- psql -v OPENAI_API_KEY=$OPENAI_API_KEY

select * from openai_list_models(:'api_key');

select openai_tokenize
( 'text-embedding-ada-002'
, $$Water, that's what I'm getting at, water. Mandrake, water is the source of all life. Seven tenths of this earth's surface is water. Why do you realize that 70% of you is water?$$
);

select vector_dims
(
    openai_embed
    ( 'text-embedding-ada-002'
    , :'OPENAI_API_KEY'
    , $$Listen, strange women lyin' in ponds distributin' swords is no basis for a system of government. Supreme executive power derives from a mandate from the masses, not from some farcical aquatic ceremony.$$
    )
);

select vector_dims(x.embedding)
from openai_embed
( 'text-embedding-ada-002'
, :'OPENAI_API_KEY'
, array
  [ $$Listen, strange women lyin' in ponds distributin' swords is no basis for a system of government.$$
  , $$Supreme executive power derives from a mandate from the masses, not from some farcical aquatic ceremony.$$
  ]
) x(embedding)
;


select jsonb_pretty
(
  openai_chat_complete
  ( 'gpt-4o'
  , :'OPENAI_API_KEY'
  , jsonb_build_array
    ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
    , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
    )
  )
);

select openai_chat_complete
( 'gpt-4o'
, :'OPENAI_API_KEY'
, jsonb_build_array
  ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
  , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
  )
)->'choices'->0->'message'->>'content'
;
