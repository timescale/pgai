

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

-------------------------------------------------------------------------------
-- execute_vectorizer by vectorizer name
create or replace function ai.execute_vectorizer(vectorizer_name pg_catalog.text) returns void
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.vectorizer
    ai.vectorizer.execute_vectorizer_by_name(plpy, vectorizer_name)
$python$
language plpython3u volatile security invoker
set search_path to pg_catalog, pg_temp
;