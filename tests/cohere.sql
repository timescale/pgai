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
, ('cohere_embed')
, ('cohere_embed-no-key')
-- add entries for new tests here!
;

-------------------------------------------------------------------------------
-- cohere_list_models
\echo cohere_list_models
select count(*) as actual
from cohere_list_models(_api_key=>$1)
\bind :cohere_api_key
\gset

update tests set
  expected = true
, actual = :actual > 0
where test = 'cohere_list_models'
;
\unset actual

-------------------------------------------------------------------------------
-- cohere_list_models-no-key
\echo cohere_list_models-no-key
select count(*) as actual
from cohere_list_models()
\gset

update tests set
  expected = true
, actual = :actual > 0
where test = 'cohere_list_models-no-key'
;
\unset actual

-------------------------------------------------------------------------------
-- cohere_list_models-endpoint
\echo cohere_list_models-endpoint
select count(*) as actual
from cohere_list_models(_endpoint=>'embed')
\gset

update tests set
  expected = true
, actual = :actual > 0
where test = 'cohere_list_models-endpoint'
;
\unset actual

-------------------------------------------------------------------------------
-- cohere_list_models-default-only
\echo cohere_list_models-default-only
select count(*) as actual
from cohere_list_models(_endpoint=>'generate', _default_only=>true)
\gset

update tests set
  expected = true
, actual = :actual > 0
where test = 'cohere_list_models-default-only'
;
\unset actual

-------------------------------------------------------------------------------
-- cohere_embed
\echo cohere_embed
select vector_dims
(
    cohere_embed
    ( 'embed-english-light-v3.0'
    , 'how much wood would a woodchuck chuck if a woodchuck could chuck wood?'
    , _api_key=>$1
    , _input_type=>'search_document'
    )
) as actual
\bind :cohere_api_key
\gset

update tests set
  expected = 384
, actual = :'actual'
where test = 'cohere_embed'
;
\unset actual

-------------------------------------------------------------------------------
-- cohere_embed-no-key
\echo cohere_embed-no-key
select vector_dims
(
    cohere_embed
    ( 'embed-english-light-v3.0'
    , 'how much wood would a woodchuck chuck if a woodchuck could chuck wood?'
    , _input_type=>'search_document'
    )
) as actual
\gset

update tests set
  expected = 384
, actual = :'actual'
where test = 'cohere_embed-no-key'
;
\unset actual
