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


create or replace view ai.secret_permissions as
SELECT * 
FROM ai._secret_permissions
WHERE to_regrole("role") is not null AND pg_has_role(current_user, "role", 'member');

create or replace function ai.grant_secret(secret_name text, grant_to_role text) returns void
as $func$
    insert into ai._secret_permissions (name, "role") VALUES (secret_name, grant_to_role);
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp;

create or replace function ai.revoke_secret(secret_name text, revoke_from_role text) returns void
as $func$
    delete from ai._secret_permissions where name = secret_name and "role" = revoke_from_role;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp;
