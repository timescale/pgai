-------------------------------------------------------------------------------
-- reveal_secret
create or replace function ai.reveal_secret(secret_name text) returns text
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.secrets
    return ai.secrets.reveal_secret(plpy, secret_name)
$python$
language plpython3u volatile security invoker
set search_path to pg_catalog, pg_temp;
