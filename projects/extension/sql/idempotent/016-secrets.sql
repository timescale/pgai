-------------------------------------------------------------------------------
-- reveal_secret
create or replace function ai.reveal_secret
( secret_name pg_catalog.text
, use_cache pg_catalog.bool default true
) returns pg_catalog.text
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.secrets
    if use_cache:
        return ai.secrets.reveal_secret(plpy, secret_name, SD)
    else:
        ai.secrets.remove_secret_from_cache(SD, secret_name)
        return ai.secrets.reveal_secret(plpy, secret_name, None)
$python$
language plpython3u stable security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- secret_permissions
create or replace view ai.secret_permissions as
select *
from ai._secret_permissions
where pg_catalog.to_regrole("role") is not null
      and pg_catalog.pg_has_role(current_user, "role", 'member');

-------------------------------------------------------------------------------
-- grant_secret
create or replace function ai.grant_secret
( secret_name pg_catalog.text
, grant_to_role pg_catalog.text
) returns void
as $func$
    insert into ai._secret_permissions ("name", "role") values (secret_name, grant_to_role);
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- revoke_secret
create or replace function ai.revoke_secret
( secret_name pg_catalog.text
, revoke_from_role pg_catalog.text
) returns void
as $func$
    delete from ai._secret_permissions
    where "name" operator(pg_catalog.=) secret_name
    and "role" operator(pg_catalog.=) revoke_from_role;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp;
