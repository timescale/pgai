-------------------------------------------------------------------------------
-- psql -v OPENAI_API_KEY=$OPENAI_API_KEY -X -f tests.sql

\set ON_ERROR_ROLLBACK 1
\set VERBOSITY verbose
\set SHOW_CONTEXT errors
\x auto

create extension if not exists ai cascade;

-------------------------------------------------------------------------------
-- use an unprivileged user "tester"
reset role; -- just in case

select count(1) filter (where rolname = 'tester') = 0 as create_tester
from pg_roles
\gset

\if :create_tester
create user tester;
\endif

select not has_schema_privilege('tester', 'public', 'create') as grant_public
\gset

\if :grant_public
grant create on schema public to tester;
\endif

select not pg_has_role(current_user, 'tester', 'member') as grant_tester
\gset

\if :grant_tester
select format('grant tester to %I', current_user)
\gexec
\endif

set role tester;

-------------------------------------------------------------------------------
-- test setup
drop table if exists tests;
create table tests
( test text not null primary key
, expected text
, actual text
, passed boolean generated always as (actual = expected) stored
);

insert into tests (test)
values
  ('openai_list_models')
, ('openai_tokenize')
, ('openai_detokenize')
, ('openai_embed-1')
, ('openai_embed-2')
, ('openai_embed-3')
, ('openai_embed-4')
, ('openai_embed-5')
, ('openai_chat_complete-1')
, ('openai_moderate')
-- add entries for new tests here!
;

-------------------------------------------------------------------------------
-- openai_list_models
select count(*) as actual
from openai_list_models($1)
\bind :OPENAI_API_KEY
\gset

update tests set 
  expected = true
, actual = :actual > 0
where test = 'openai_list_models'
;
\unset actual

-------------------------------------------------------------------------------
-- openai_tokenize
select openai_tokenize('text-embedding-ada-002', 'the purple elephant sits on a red mushroom') as actual
\gset

update tests set
  expected = array[1820,25977,46840,23874,389,264,2579,58466]::text
, actual = :'actual'::int[]::text
where test = 'openai_tokenize'
;
\unset actual

-------------------------------------------------------------------------------
-- openai_detokenize
select openai_detokenize('text-embedding-ada-002', array[1820,25977,46840,23874,389,264,2579,58466]) as actual
\gset

update tests set
  expected = 'the purple elephant sits on a red mushroom'
, actual = :'actual'
where test = 'openai_detokenize'
;
\unset actual

-------------------------------------------------------------------------------
-- openai_embed-1
select vector_dims
(
    openai_embed
    ( $1
    , 'text-embedding-ada-002'
    , 'the purple elephant sits on a red mushroom'
    )
) as actual
\bind :OPENAI_API_KEY
\gset

update tests set
  expected = 1536
, actual = :'actual'
where test = 'openai_embed-1'
;
\unset actual

-------------------------------------------------------------------------------
-- openai_embed-2
select vector_dims
(
    openai_embed
    ( $1
    , 'text-embedding-3-large'
    , 'the purple elephant sits on a red mushroom'
    , _dimensions=>768
    )
) as actual
\bind :OPENAI_API_KEY
\gset

update tests set 
  expected = 768
, actual = :'actual'
where test = 'openai_embed-2'
;
\unset actual

-------------------------------------------------------------------------------
-- openai_embed-3
select vector_dims
(
    openai_embed
    ( $1
    , 'text-embedding-3-large'
    , 'the purple elephant sits on a red mushroom'
    , _user=>'bob'
    )
) as actual
\bind :OPENAI_API_KEY
\gset

update tests set 
  expected = 3072
, actual = :'actual'
where test = 'openai_embed-3'
;
\unset actual

-------------------------------------------------------------------------------
-- openai_embed-4
select sum(vector_dims(embedding)) as actual
from openai_embed
( $1
, 'text-embedding-3-large'
, array['the purple elephant sits on a red mushroom', 'timescale is postgres made powerful']
)
\bind :OPENAI_API_KEY
\gset

update tests set 
  expected = 6144
, actual = :'actual'
where test = 'openai_embed-4'
;
\unset actual

-------------------------------------------------------------------------------
-- openai_embed-5
select vector_dims
(
    openai_embed
    ( $1
    , 'text-embedding-ada-002'
    , array[1820,25977,46840,23874,389,264,2579,58466]
    )
) as actual
\bind :OPENAI_API_KEY
\gset

update tests set 
  expected = 1536
, actual = :'actual'
where test = 'openai_embed-5'
;
\unset actual

-------------------------------------------------------------------------------
-- openai_chat_complete-1
select openai_chat_complete
( $1
, 'gpt-4o'
, jsonb_build_array
  ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
  , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
  )
) as actual
\bind :OPENAI_API_KEY
\gset

select jsonb_extract_path_text(:'actual'::jsonb, 'choices', '0', 'message', 'content') is not null as actual
\gset

update tests set 
  expected = true::text
, actual = :'actual'::bool::text
where test = 'openai_chat_complete-1'
;
\unset actual

-------------------------------------------------------------------------------
-- openai_moderate

select openai_moderate
( $1
, 'text-moderation-stable'
, 'I want to kill them.'
) as actual
\bind :OPENAI_API_KEY
\gset

select jsonb_extract_path_text(:'actual'::jsonb, 'results', '0', 'flagged')::bool as actual
\gset

update tests set 
  expected = true::text
, actual = :'actual'::bool::text
where test = 'openai_moderate'
;
\unset actual

-------------------------------------------------------------------------------
-- results
select test, passed
from tests
;

select *
from tests
where not passed
;

select
  count(*) as run
, count(*) filter (where passed = true) as passed
, count(*) filter (where passed = false) as failed
, count(*) filter (where passed is null) as did_not_run
from tests
;

select count(*) filter (where passed = false or passed is null) = 0 as result
from tests
\gset

reset role; -- no longer tester

\if :result
\echo PASSED!
\else
\warn FAILED!
\set ON_ERROR_STOP 1
do $$
begin
raise exception 'FAILED!';
end;
$$;
\endif
\q
