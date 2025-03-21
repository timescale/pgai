
create extension ai cascade;

create schema wiki;
grant usage on schema wiki to jill;

create table wiki.post
( id serial not null primary key
, title text not null
, published timestamptz
, category text
, tags text[]
, content text not null
);
grant select on wiki.post to jill;

select ai.grant_ai_usage('jill');
