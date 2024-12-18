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

select jsonb_pretty
( to_jsonb(x)
  #- array['config', 'version']
  #- array['config', 'embedding', 'base_url']
)
from ai.vectorizer x
order by id
;

\pset title 'i need a function about life'
select objtype, objnames, objargs, description from ai.find_relevant_obj('i need a function about life');

\pset title 'i need a function about life only_objtype=>function'
select objtype, objnames, objargs, description from ai.find_relevant_obj('i need a function about life', objtypes=>array['function']);

\pset title 'i need a function about life max_dist=>0.4'
select objtype, objnames, objargs, description from ai.find_relevant_obj('i need a function about life', max_dist=>0.4);

\pset title 'i need a query to tell me about bobbys life'
select sql, description from ai.find_relevant_sql('i need a query to tell me about bobby''s life');
