
/*
roles cannot belong to an extension and they exist at the cluster level
if our extension creates roles, this will cause issues for
* dump/restore
* testing
* different versions of the extension running in different databases of the SAME cluster

instead of creating roles we will create a function that is called with a role as an argument to embue an
existing role with privileges to utilize various aspects of pgai

this functions would be security definer
since our extension has to be created by a superuser anyway, this is okay
our pgai functions/tables/views are all in the ai schema, which no one but the extension-creator will have access to
by default
the superuser can call the function on roles that should be granted privileges to pgai

benefits:
the extension itself does not modify ANYTHING at the database cluster level. it is fully contained at the database level
easier to test
easier to dump/restore
multiple versions of the extension in the same cluster cannot mess with each other
*/

create function ai.grant_ai_usage(_user regrole, _with_grant bool default false) returns void
as $func$
declare
    _rec record;
begin
    -- schema
    execute pg_catalog.format
    ( $$grant usage on schema ai to %I%s$$
    , _user
    , case when _with_grant then ' with grant option;' else ';' end
    );

    -- tables & sequences
    for _rec in
    (
        select
            n.nspname,
            k.relname,
            case k.relkind
                when 'S' then 'sequence'
                else 'table'
            end as kind
        from pg_catalog.pg_class k
        inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
        where k.relkind in ('r', 'p', 'S') -- tables and sequences
        and n.nspname operator(pg_catalog.=) 'ai'
        order by k.relkind, n.nspname, k.relname
    )
    loop
        execute pg_catalog.format
        ( 'grant all privileges on %s %I.%I to %s%s'
        , _rec.kind
        , _rec.nspname
        , _rec.relname
        , _user
        , case when _with_grant then ' with grant option;' else ';' end
        );
    end loop;

    -- functions & procedures
    for _rec in
    (
        select
          case prokind
              when 'f' then 'function'
              when 'p' then 'procedure'
          end as prokind
        , n.nspname
        , k.proname
        , pg_get_function_identity_arguments(k.oid) as args
        from pg_catalog.pg_depend d
        inner join pg_catalog.pg_extension e on (d.refobjid operator(pg_catalog.=) e.oid)
        inner join pg_catalog.pg_proc k on (d.objid operator(pg_catalog.=) k.oid)
        inner join pg_namespace n on (k.pronamespace operator(pg_catalog.=) n.oid)
        where d.refclassid operator(pg_catalog.=) 'pg_catalog.pg_extension'::pg_catalog.regclass
        and d.deptype operator(pg_catalog.=) 'e'
        and e.extname operator(pg_catalog.=) 'ai'
        and k.prokind in ('f', 'p')
        and case when _with_grant then true else k.proname operator(pg_catalog.!=) 'grant_ai_user' end
    )
    loop
        execute pg_catalog.format
        ( $$grant execute on %s %I.%I(%s) to %I%s$$
        , _rec.prokind
        , _rec.nspname
        , _rec.proname
        , _rec.args
        , _user
        , case when _with_grant then ' with grant option;' else ';' end
        );
    end loop;
end;
$func$ language plpgsql volatile security definer
set search_path to pg_catalog, pg_temp
;
