

select * from ai.openai_list_models(:'api_key');

select ai.openai_tokenize
( 'text-embedding-ada-002'
, $$Water, that's what I'm getting at, water. Mandrake, water is the source of all life. Seven tenths of this earth's surface is water. Why do you realize that 70% of you is water?$$
);

select vector_dims
(
    ai.openai_embed
    ( 'text-embedding-ada-002'
    , :'api_key'
    , $$Listen, strange women lyin' in ponds distributin' swords is no basis for a system of government. Supreme executive power derives from a mandate from the masses, not from some farcical aquatic ceremony.$$
    )
);

select vector_dims(x.embedding)
from ai.openai_embed
( 'text-embedding-ada-002'
, :'api_key'
, array
  [ $$Listen, strange women lyin' in ponds distributin' swords is no basis for a system of government.$$
  , $$Supreme executive power derives from a mandate from the masses, not from some farcical aquatic ceremony.$$
  ]
) x(embedding)
;

