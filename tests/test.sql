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

select not has_schema_privilege('tester', 'public', 'create') as do_grant
\gset

\if :do_grant
grant create on schema public to tester;
\endif
\unset do_grant

select not pg_has_role(current_user, 'tester', 'member') as do_grant
\gset

\if :do_grant
select format('grant tester to %I', current_user)
\gexec
\endif
\unset do_grant

select not has_function_privilege('tester', 'pg_read_binary_file(text)', 'execute') as do_grant
\gset

\if :do_grant
grant execute on function pg_read_binary_file(text) to tester;
\endif
\unset do_grant

select not pg_has_role('tester', 'pg_read_server_files', 'member') as do_grant
\gset

\if :do_grant
grant pg_read_server_files to tester;
\endif
\unset do_grant

select not has_schema_privilege('tester', 'ai', 'usage') as do_grant
\gset

\if :do_grant
grant usage on schema ai to tester;
\endif
\unset do_grant

set role tester;

-------------------------------------------------------------------------------
-- test table
drop table if exists tests;
create table tests
( test text not null primary key
, expected text
, actual text
, passed boolean generated always as (actual = expected) stored
);

-------------------------------------------------------------------------------
-- convenience function for recording test results
create function result(_test text, _expected text, _actual text) returns bool
as $func$
merge into tests as t
using (select _test as test, _expected as expected, _actual as actual) x
on (t.test = x.test)
when matched then update set expected = x.expected, actual = x.actual
when not matched then insert (test, actual) values (x.test, x.actual)
;
select passed from tests where test = _test;
$func$ language sql;

\pset tuples_only on
-------------------------------------------------------------------------------
-- openai tests
\getenv enable_openai_tests ENABLE_OPENAI_TESTS
\if :{?enable_openai_tests}
\else
\set enable_openai_tests 0
\endif
\if :enable_openai_tests
\set ON_ERROR_ROLLBACK on
\set ON_ERROR_STOP off
\i tests/openai.sql
\set ON_ERROR_ROLLBACK off
\set ON_ERROR_STOP on
\else
\echo Skipped OpenAI tests
\endif

-------------------------------------------------------------------------------
-- ollama tests
\getenv enable_ollama_tests ENABLE_OLLAMA_TESTS
\if :{?enable_ollama_tests}
\else
\set enable_ollama_tests 0
\endif
\if :enable_ollama_tests
\set ON_ERROR_ROLLBACK on
\set ON_ERROR_STOP off
\i tests/ollama.sql
\set ON_ERROR_ROLLBACK off
\set ON_ERROR_STOP on
\else
\echo Skipped Ollama tests
\endif

-------------------------------------------------------------------------------
-- anthropic tests
\getenv enable_anthropic_tests ENABLE_ANTHROPIC_TESTS
\if :{?enable_anthropic_tests}
\else
\set enable_anthropic_tests 0
\endif
\if :enable_anthropic_tests
\set ON_ERROR_ROLLBACK on
\set ON_ERROR_STOP off
\i tests/anthropic.sql
\set ON_ERROR_ROLLBACK off
\set ON_ERROR_STOP on
\else
\echo Skipped Anthropic tests
\endif

-------------------------------------------------------------------------------
-- cohere tests
\getenv enable_cohere_tests ENABLE_COHERE_TESTS
\if :{?enable_cohere_tests}
\else
\set enable_cohere_tests 0
\endif
\if :enable_cohere_tests
\set ON_ERROR_ROLLBACK on
\set ON_ERROR_STOP off
\i tests/cohere.sql
\set ON_ERROR_ROLLBACK off
\set ON_ERROR_STOP on
\else
\echo Skipped Cohere tests
\endif

\pset tuples_only off
-------------------------------------------------------------------------------
-- test results
\echo
\echo
\echo
\echo
\echo

\set ON_ERROR_STOP on
\set ON_ERROR_ROLLBACK off

-- we should fail if no tests were run
select count(*) > 0 as result
from tests
\gset

\if :result

    \echo test results
    select test, passed
    from tests
    ;

    \echo failed tests
    select *
    from tests
    where passed is distinct from true
    ;

    \echo test stats
    select
      count(*) as total
    , count(*) filter (where passed = true) as passed
    , count(*) filter (where passed is distinct from true) as failed
    from tests
    ;

    select count(*) filter (where passed is distinct from true) = 0 as result
    from tests
    \gset

\else
\warn NO TESTS WERE RUN!
\endif


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
