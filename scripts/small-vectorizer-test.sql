create extension ai cascade;
create extension if not exists timescaledb;

create schema if not exists website;

drop table if exists website.blog;
create table website.blog
( id int not null generated always as identity
, title text not null
, published timestamptz
, body text not null
, primary key (title, published)
);

insert into website.blog(title, published, body)
values
  ('how to cook a hot dog', '2024-01-06'::timestamptz, 'put it on a hot grill')
, ('how to make a sandwich', '2023-01-06'::timestamptz, 'put a slice of meat between two pieces of bread')
, ('how to make stir fry', '2022-01-06'::timestamptz, 'pick up the phone and order takeout')
;

-- create a vectorizer
select ai.create_vectorizer
( 'website.blog'::regclass
, embedding=>ai.embedding_openai('text-embedding-3-small', 1536)
, chunking=>ai.chunking_recursive_character_text_splitter('body')
, formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
, scheduling=>ai.scheduling_timescaledb
        ( interval '5m'
        , initial_start=>'2050-01-06'::timestamptz -- don't start it for a long time!
        , timezone=>'America/Chicago'
        )
) as vectorizer_id
\gset

-- view the vectorizer row
select jsonb_pretty(to_jsonb(x))
from ai.vectorizer x
where x.id = :vectorizer_id
;

-- view the background job
select j.*
from timescaledb_information.jobs j
inner join ai.vectorizer x on (j.job_id = (x.config->'scheduling'->>'job_id')::int)
where x.id = :vectorizer_id
;

-- how many items in the queue?
select ai.vectorizer_queue_pending(:vectorizer_id);

-- send the http request
select ai.execute_vectorizer(:vectorizer_id);

-- how many items in the queue?
select ai.vectorizer_queue_pending(:vectorizer_id)
\watch 10
