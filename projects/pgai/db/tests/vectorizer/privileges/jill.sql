
select count(*)
from wiki.post
;

select count(*)
from wiki.post_embedding
;

select count(*)
from wiki.post_embedding_store
;

select ai.vectorizer_queue_pending(1);

select count(*)
from ai._vectorizer_q_1
;

select count(*)
from ai.vectorizer_status
;

select count(*)
from ai.vectorizer_errors
;

select id as vectorizer_id
from ai.vectorizer
where source_table = 'post'
\gset

select ai.disable_vectorizer_schedule(:vectorizer_id);

select ai.enable_vectorizer_schedule(:vectorizer_id);

