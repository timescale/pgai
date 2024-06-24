-------------------------------------------------------------------------------
-- pgai tests
\set VERBOSITY verbose
\set SHOW_CONTEXT errors
\x auto
\set ON_ERROR_ROLLBACK off
\set ON_ERROR_STOP on

-------------------------------------------------------------------------------
-- drop (if exists), recreate, and connect to the "test" database
select current_database() != 'postgres' as switch_db
\gset
\if :switch_db
\c postgres
\endif

select count(*) > 0 as drop_test_db
from pg_catalog.pg_database
where datname = 'test'
\gset

\if :drop_test_db
drop database test;
\endif

create database test;
\c test

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

select not has_function_privilege('tester', 'pg_read_binary_file(text)', 'execute') as grant_pg_read_server_files
\gset

\if :grant_pg_read_server_files
grant execute on function pg_read_binary_file(text) to tester;
\endif

select not pg_has_role('tester', 'pg_read_server_files', 'member') as grant_tester
\gset

\if :grant_tester
grant pg_read_server_files to tester;
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

-------------------------------------------------------------------------------
-- openai tests
\getenv enable_openai_tests ENABLE_OPENAI_TESTS
\if :enable_openai_tests
\set ON_ERROR_ROLLBACK on
\set ON_ERROR_STOP off
\i tests/openai.sql
\set ON_ERROR_ROLLBACK off
\set ON_ERROR_STOP on
\endif

-------------------------------------------------------------------------------
-- ollama tests
\getenv enable_ollama_tests ENABLE_OLLAMA_TESTS
\if :enable_ollama_tests
\set ON_ERROR_ROLLBACK on
\set ON_ERROR_STOP off
\i tests/ollama.sql
\set ON_ERROR_ROLLBACK off
\set ON_ERROR_STOP on
\endif

-------------------------------------------------------------------------------
-- anthropic tests
\getenv enable_anthropic_tests ENABLE_ANTHROPIC_TESTS
\if :enable_anthropic_tests
\set ON_ERROR_ROLLBACK on
\set ON_ERROR_STOP off
\i tests/anthropic.sql
\set ON_ERROR_ROLLBACK off
\set ON_ERROR_STOP on
\endif

-------------------------------------------------------------------------------
-- test results
\echo
\echo
\echo test results
\echo
\echo

\set ON_ERROR_STOP on
\set ON_ERROR_ROLLBACK off
\echo test results
select test, passed
from tests
;

\echo failed tests
select *
from tests
where not passed
;

\echo test stats
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
do $$
begin
raise exception 'FAILED!';
end;
$$;
\endif
\q
