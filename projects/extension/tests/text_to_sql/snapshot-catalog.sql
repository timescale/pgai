\pset pager off

\d+ ai._vectorizer_q_1
\d+ ai._vectorizer_q_2
\d+ ai.semantic_catalog_obj_1_store
\d+ ai.semantic_catalog_sql_1_store
\d+ ai.semantic_catalog_obj_1
\d+ ai.semantic_catalog_sql_1

select * from ai.semantic_catalog order by id;
select objtype, objnames, objargs, description from ai.semantic_catalog_obj order by objtype, objnames, objargs;
select * from ai.semantic_catalog_sql order by id;
select objtype, objnames, objargs from ai._vectorizer_q_1 order by objtype, objnames, objargs;
select id from ai._vectorizer_q_2 order by id;
select * from ai.vectorizer_status order by id;

select jsonb_pretty(to_jsonb(x) #- array['config', 'version'])
from ai.vectorizer x
order by id
;
