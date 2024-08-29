create extension if not exists timescaledb;
create extension if not exists ai cascade;

create table blog
( id int not null primary key generated always as identity
, title text not null
, published timestamptz
, content text not null
, category text not null
, tags jsonb
);

insert into blog (title, published, content, category, tags)
values
  ('how to cook a hot dog', '2024-01-06'::timestamptz, 'put it on a hot grill', 'easy', '["grill"]'::jsonb)
, ('how to make a sandwich', '2023-01-06'::timestamptz, 'put a slice of meat between two pieces of bread', 'easy', '["no cook"]'::jsonb)
, ('how to make stir fry', '2022-01-06'::timestamptz, 'pick up the phone and order takeout', 'easy', '["phone-required"]'::jsonb)
;

select ai.create_vectorizer
( 'blog'::regclass
, embedding=>ai.embedding_openai('text-embedding-3-small', 768)
, chunking=>ai.chunking_character_text_splitter('content', 128, 10)
, formatting=>ai.formatting_python_template
        ( 'title: $title published: $published $chunk'
        , columns=>array['title', 'published']
        )
, scheduling=>ai.scheduling_timescaledb
        ( interval '5m'
        , initial_start=>'2050-01-06'::timestamptz
        , timezone=>'America/Chicago'
        )
, grant_to=>null
);

