
create schema wiki;
create table wiki.post
( id serial not null primary key
, title text not null
, published timestamptz
, category text
, tags text[]
, content text not null
);
