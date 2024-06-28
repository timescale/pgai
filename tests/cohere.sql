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
-- add entries for new tests here!
;

-------------------------------------------------------------------------------
-- cohere_list_models
\echo cohere_list_models
select count(*) as actual
from cohere_list_models(_api_key=>$1)
\bind :cohere_api_key
\gset

select result('cohere_list_models', true, :actual > 0);
\unset actual

-------------------------------------------------------------------------------
-- cohere_list_models-no-key
\echo cohere_list_models-no-key
select count(*) as actual
from cohere_list_models()
\gset

select result('cohere_list_models-no-key', true, :actual > 0);
\unset actual

-------------------------------------------------------------------------------
-- cohere_list_models-endpoint
\echo cohere_list_models-endpoint
select count(*) as actual
from cohere_list_models(_endpoint=>'embed')
\gset

select result('cohere_list_models-endpoint', true, :actual > 0);
\unset actual

-------------------------------------------------------------------------------
-- cohere_tokenize
\echo cohere_tokenize
select cohere_tokenize
( 'command'
, 'What one programmer can do in one month, two programmers can do in two months.'
, _api_key=>$1
) as actual
\bind :cohere_api_key
\gset

select result('cohere_tokenize', 17, array_length(:'actual'::int[], 1));
\unset actual

-------------------------------------------------------------------------------
-- cohere_tokenize-no-key
\echo cohere_tokenize-no-key
select cohere_tokenize
( 'command'
, 'One of the best programming skills you can have is knowing when to walk away for awhile.'
) as actual
\gset

select result('cohere_tokenize-no-key', '{5256,1707,1682,2383,9461,4696,1739,1863,1871,1740,9397,2112,1705,4066,3465,1742,38700,21}', :'actual');
\unset actual

-------------------------------------------------------------------------------
-- cohere_detokenize
\echo cohere_detokenize
select cohere_detokenize
( 'command'
, array[5171,2011,36613,1863,1978,1703,2011,2812,19,2253,38374,1863,1978,1703,2253,3784,21]
, _api_key=>$1
) as actual
\bind :cohere_api_key
\gset

select result('cohere_detokenize', 'What one programmer can do in one month, two programmers can do in two months.', :'actual');
\unset actual

-------------------------------------------------------------------------------
-- cohere_detokenize-no-key
\echo cohere_detokenize-no-key
select cohere_detokenize
( 'command'
, array[14485,38374,2630,2060,2252,5164,4905,21,2744,2628,1675,3094,23407,21]
) as actual
\gset

select result('cohere_detokenize-no-key', $$Good programmers don't just write programs. They build a working vocabulary.$$, :'actual');
\unset actual

-------------------------------------------------------------------------------
-- cohere_list_models-default-only
\echo cohere_list_models-default-only
select count(*) as actual
from cohere_list_models(_endpoint=>'generate', _default_only=>true)
\gset

select result('cohere_list_models-default-only', true, :actual > 0);
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

select result('cohere_embed', 384, :actual);
\unset actual

-------------------------------------------------------------------------------
-- cohere_embed-no-key
\echo cohere_embed-no-key
select vector_dims
(
    cohere_embed
    ( 'embed-english-light-v3.0'
    , 'if a woodchuck could chuck wood, a woodchuck would chuck as much wood as he could'
    , _input_type=>'search_document'
    , _truncate=>'end'
    )
) as actual
\gset

select result('cohere_embed-no-key', 384, :actual);
\unset actual
