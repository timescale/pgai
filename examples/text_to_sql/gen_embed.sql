
-- generate embeddings for the obj descriptions
insert into ai.semantic_catalog_obj_1_store(embedding_uuid, objtype, objnames, objargs, chunk_seq, chunk, embedding)
select
  gen_random_uuid()
, objtype, objnames, objargs
, 0
, description
, ai.openai_embed('text-embedding-3-small', description, dimensions=>1024)
from ai.semantic_catalog_obj
;
delete from ai._vectorizer_q_1;
