-------------------------------------------------------------------------------
-- get our ollama host
-- grab our ollama host from the environment as a psql variable
\getenv ollama_host OLLAMA_HOST
\if :{?ollama_host}
\else
\warn Ollama tests are enabled but OLLAMA_HOST is not set!
do $$
begin
raise exception 'vectorize tests are enabled but OLLAMA_HOST is not set!';
end;
$$;
\q
\endif

-- set our session local GUC
select set_config('ai.ollama_host', $1, false) is not null as set_ollama_host
\bind :ollama_host
\g

-------------------------------------------------------------------------------
-- register our tests
insert into tests (test)
values
  ('vectorize_id')
, ('vectorize_embed_table_exists')
, ('vectorize_queue_table_exists')
, ('vectorize_queue_has_row')
-- add entries for new tests here!
;

-------------------------------------------------------------------------------
-- create the source table
create schema website;
create table website.blog
( id int not null generated always as identity -- deliberately not primary key
, title text not null
, published timestamptz
, body text
, primary key (title, published)
);

-- insert a row into the source table
insert into website.blog (title, published, body)
values
  ('hot dog recipe', '2024-01-06'::timestamptz, 'put the hot dog on a hot grill until it is cooked')
;

-------------------------------------------------------------------------------
-- vectorize_id
\set testname vectorize_id
\echo :testname

select ai.vectorize
( 'website.blog'::regclass
, array['body']::name[]
, 4096
) as actual
\gset

select id as expected
from ai.vectorize v
where source_schema = 'website'
and source_table = 'blog'
and source_cols = array['body']::name[]
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- vectorize_embed_table_exists
\set testname vectorize_embed_table_exists
\set expected t
\echo :testname

select to_regclass('website.blog_embedding') is not null as actual
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- vectorize_queue_table_exists
\set testname vectorize_queue_table_exists
\set expected t
\echo :testname

select to_regclass('website.blog_embedding_q') is not null as actual
\gset

\ir eval.sql

-------------------------------------------------------------------------------
-- vectorize_queue_has_row
\set testname vectorize_queue_has_row
\set expected 1
\echo :testname

select count(*) as actual
from website.blog_embedding_q
\gset

\ir eval.sql
