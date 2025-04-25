

-------------------------------------------------------------------------------
-- execute_vectorizer
create or replace function ai.execute_vectorizer(vectorizer_id pg_catalog.int4) returns void
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.vectorizer
    ai.vectorizer.execute_vectorizer(plpy, vectorizer_id)
$python$
language plpython3u volatile security invoker
set search_path to pg_catalog, pg_temp
;
       
create or replace function ai.execute_vectorizer(name pg_catalog.text) returns void
as $func$
   select ai.execute_vectorizer(v.id)
   from ai.vectorizer v
   where v.name operator(pg_catalog.=) drop_vectorizer.name;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;