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

select ai.grant_vectorizer_usage('jill');

select ai.create_vectorizer
( 'wiki.post'::regclass
, loading=>ai.loading_column(column_name=>'content')
, embedding=>ai.embedding_openai('text-embedding-3-small', 768)
, chunking=>ai.chunking_character_text_splitter(128, 10)
, scheduling=>ai.scheduling_none()
, indexing=>ai.indexing_none()
, grant_to=>ai.grant_to('fred', 'jill')
);