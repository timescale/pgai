-------------------------------------------------------------------------------
-- get our cohere api key
\getenv cohere_api_key COHERE_API_KEY
-- set our session local GUC
select set_config('ai.cohere_api_key', $1, false) is not null as set_cohere_api_key
\bind :cohere_api_key
\g

-------------------------------------------------------------------------------
-- register our tests
insert into tests (test)
values
  ('cohere_list_models')
, ('cohere_list_models-no-key')
, ('cohere_list_models-endpoint')
, ('cohere_list_models-default-only')
, ('cohere_tokenize')
, ('cohere_tokenize-no-key')
, ('cohere_detokenize')
, ('cohere_detokenize-no-key')
, ('cohere_embed')
, ('cohere_embed-no-key')
, ('cohere_classify')
, ('cohere_classify_simple')
, ('cohere_rerank')
, ('cohere_rerank_simple')
, ('cohere_chat_complete')
-- add entries for new tests here!
;

-------------------------------------------------------------------------------
-- cohere_chat_complete
\echo cohere_chat_complete

select cohere_chat_complete
( 'command-r-plus'
, 'How much wood would a woodchuck chuck if a woodchuck could chuck wood?'
, _seed=>42
)->>'text' is not null as actual
\gset

select result('cohere_chat_complete', true, :'actual'::bool);
\unset actual
