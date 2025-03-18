select ai.drop_vectorizer(id) from ai.vectorizer;

select ai.create_vectorizer(
  'public.wiki'::regclass,
  embedding=>ai.embedding_openai('text-embedding-3-small', 1536),
  loading =>ai.loading_column('body'),
  chunking=>ai.chunking_recursive_character_text_splitter(),
  formatting=>ai.formatting_python_template('title: $title $chunk'),
  processing=>ai.processing_default(
    batch_size=>50,
    concurrency=>1
  )
);

\if :total_items
  delete from wiki where id not in (select id from wiki order by id limit :total_items);
\endif

\if :repeat_content
  update wiki set body = repeat(body, :repeat_content)
\endif
