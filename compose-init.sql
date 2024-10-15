create extension if not exists ai cascade;

create schema website;
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
, scheduling=>ai.scheduling_none()
, indexing=>ai.indexing_none()
) as vectorizer_id
