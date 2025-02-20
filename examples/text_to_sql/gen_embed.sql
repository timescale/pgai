
-- generate embeddings for the obj descriptions
insert into ai.semantic_catalog_obj_1_store(embedding_uuid, id, chunk_seq, chunk, embedding)
select
  gen_random_uuid()
, o.id
, 0
, o.description
, ai.openai_embed('text-embedding-3-small', o.description, dimensions=>1024)
from ai.semantic_catalog_obj o
;
delete from ai._vectorizer_q_1;
