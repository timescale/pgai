create schema wiki;

create table wiki.blog
( id int not null primary key generated always as identity
, title text not null
, published timestamptz
, content text not null
, category text not null
, tags jsonb
);

insert into wiki.blog (title, published, content, category, tags)
values
  ('how to cook a hot dog', '2024-01-06'::timestamptz, 'put it on a hot grill', 'easy', '["grill"]'::jsonb)
, ('how to make a sandwich', '2023-01-06'::timestamptz, 'put a slice of meat between two pieces of bread', 'easy', '["no cook"]'::jsonb)
, ('how to make stir fry', '2022-01-06'::timestamptz, 'pick up the phone and order takeout', 'easy', '["phone-required"]'::jsonb)
;

select ai.create_vectorizer
( 'wiki.blog'::regclass
, embedding=>ai.embedding_openai('text-embedding-3-small', 768)
, chunking=>ai.chunking_character_text_splitter('content', 128, 10)
, formatting=>ai.formatting_python_template('title: $title published: $published $chunk')
, scheduling=>ai.scheduling_none()
, indexing=>ai.indexing_none()
, grant_to=>ai.grant_to('vera')
);

select ai.grant_secret('top_secret_password', 'vera')
