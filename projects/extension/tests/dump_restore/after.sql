
create schema wiki;
create table wiki.post
( id serial not null primary key
, title text not null
, published timestamptz
, category text
, tags text[]
, content text not null
);

select ai.create_vectorizer
( 'wiki.post'::regclass
, embedding=>ai.embedding_openai('text-embedding-3-small', 768)
, chunking=>ai.chunking_character_text_splitter('content', 128, 10)
, scheduling=>ai.scheduling_none()
, indexing=>ai.indexing_none()
, grant_to=>null
);

