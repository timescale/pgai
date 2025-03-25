select ai.drop_vectorizer(id) from ai.vectorizer;

select ai.create_vectorizer(
  'public.wiki'::regclass,
  embedding=>ai.embedding_openai('text-embedding-3-small', 1536),
  chunking=>ai.chunking_recursive_character_text_splitter('body'),
  formatting=>ai.formatting_python_template('title: $title $chunk'),
  processing=>ai.processing_default(
    batch_size=>20,
    concurrency=>1
  )
);
