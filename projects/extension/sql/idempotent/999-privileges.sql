
-------------------------------------------------------------------------------
-- grant_ai_usage
create or replace function ai.grant_ai_usage(to_user pg_catalog.name, admin pg_catalog.bool default false) returns void
as $func$
declare
    _sql pg_catalog.text;
begin
    -- schema
    select pg_catalog.format
    ( 'grant %s on schema ai to %I%s'
    , case when admin then 'all privileges' else 'usage, create' end
    , to_user
    , case when admin then ' with grant option' else '' end
    ) into strict _sql
    ;
    raise debug '%', _sql;
    execute _sql;

    -- tables, sequences, and views
    for _sql in
    (
        select pg_catalog.format
        ( 'grant %s on %s %I.%I to %I%s'
        , case
            when admin then 'all privileges'
            else
                case
                    when k.relname operator(pg_catalog.=) 'semantic_catalog' then 'select'
                    when k.relkind in ('r', 'p') then 'select, insert, update, delete'
                    when k.relkind in ('S') then 'usage, select, update'
                    when k.relkind in ('v') then 'select'
                end
          end
        , case
            when k.relkind in ('r', 'p') then 'table'
            when k.relkind in ('S') then 'sequence'
            when k.relkind in ('v') then ''
          end
        , n.nspname
        , k.relname
        , to_user
        , case when admin then ' with grant option' else '' end
        )
        from pg_catalog.pg_depend d
        inner join pg_catalog.pg_extension e on (d.refobjid operator(pg_catalog.=) e.oid)
        inner join pg_catalog.pg_class k on (d.objid operator(pg_catalog.=) k.oid)
        inner join pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
        where d.refclassid operator(pg_catalog.=) 'pg_catalog.pg_extension'::pg_catalog.regclass
        and d.deptype operator(pg_catalog.=) 'e'
        and e.extname operator(pg_catalog.=) 'ai'
        and k.relkind in ('r', 'p', 'S', 'v') -- tables, sequences, and views
        and (admin, n.nspname, k.relname) not in
        ( (false, 'ai', 'migration') -- only admins get any access to this table
        , (false, 'ai', '_secret_permissions') -- only admins get any access to this table
        , (false, 'ai', 'feature_flag') -- only admins get any access to this table
        )
        order by n.nspname, k.relname
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;

    -- procedures and functions
    for _sql in
    (
        select pg_catalog.format
        ( 'grant %s on %s %I.%I(%s) to %I%s'
        , case when admin then 'all privileges' else 'execute' end
        , case k.prokind
              when 'f' then 'function'
              when 'p' then 'procedure'
          end
        , n.nspname
        , k.proname
        , pg_catalog.pg_get_function_identity_arguments(k.oid)
        , to_user
        , case when admin then ' with grant option' else '' end
        )
        from pg_catalog.pg_depend d
        inner join pg_catalog.pg_extension e on (d.refobjid operator(pg_catalog.=) e.oid)
        inner join pg_catalog.pg_proc k on (d.objid operator(pg_catalog.=) k.oid)
        inner join pg_namespace n on (k.pronamespace operator(pg_catalog.=) n.oid)
        where d.refclassid operator(pg_catalog.=) 'pg_catalog.pg_extension'::pg_catalog.regclass
        and d.deptype operator(pg_catalog.=) 'e'
        and e.extname operator(pg_catalog.=) 'ai'
        and k.prokind in ('f', 'p')
        and case
              when k.proname in
                ( 'grant_ai_usage'
                , 'grant_secret'
                , 'revoke_secret'
                , 'post_restore'
                , 'initialize_semantic_catalog'
                )
              then admin -- only admins get these function
              else true
            end
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;
    
    -- secret permissions
    if admin then
        -- grant access to all secrets to admin users
        insert into ai._secret_permissions ("name", "role")
        values ('*', to_user)
        on conflict on constraint _secret_permissions_pkey
        do nothing
        ;
    end if;
end
$func$ language plpgsql volatile
security invoker -- gotta have privs to give privs
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- grant admin usage to session user and pg_database_owner
select ai.grant_ai_usage(pg_catalog."session_user"(), admin=>true);
select ai.grant_ai_usage('pg_database_owner', admin=>true);

-------------------------------------------------------------------------------
-- revoke everything from public
do language plpgsql $func$
declare
    _sql text;
begin
    -- schema
    revoke all privileges on schema ai from public;

    -- tables, sequences, and views
    for _sql in
    (
        select pg_catalog.format
        ( 'revoke all privileges on %s %I.%I from public'
        , case
            when k.relkind in ('r', 'p') then 'table'
            when k.relkind in ('S') then 'sequence'
            when k.relkind in ('v') then ''
          end
        , n.nspname
        , k.relname
        )
        from pg_catalog.pg_depend d
        inner join pg_catalog.pg_extension e on (d.refobjid operator(pg_catalog.=) e.oid)
        inner join pg_catalog.pg_class k on (d.objid operator(pg_catalog.=) k.oid)
        inner join pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
        where d.refclassid operator(pg_catalog.=) 'pg_catalog.pg_extension'::pg_catalog.regclass
        and d.deptype operator(pg_catalog.=) 'e'
        and e.extname operator(pg_catalog.=) 'ai'
        and k.relkind in ('r', 'p', 'S', 'v') -- tables, sequences, and views
        order by n.nspname, k.relname
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;

    -- procedures and functions
    for _sql in
    (
        select pg_catalog.format
        ( 'revoke all privileges on %s %I.%I(%s) from public'
        , case k.prokind
              when 'f' then 'function'
              when 'p' then 'procedure'
          end
        , n.nspname
        , k.proname
        , pg_catalog.pg_get_function_identity_arguments(k.oid)
        )
        from pg_catalog.pg_depend d
        inner join pg_catalog.pg_extension e on (d.refobjid operator(pg_catalog.=) e.oid)
        inner join pg_catalog.pg_proc k on (d.objid operator(pg_catalog.=) k.oid)
        inner join pg_namespace n on (k.pronamespace operator(pg_catalog.=) n.oid)
        where d.refclassid operator(pg_catalog.=) 'pg_catalog.pg_extension'::pg_catalog.regclass
        and d.deptype operator(pg_catalog.=) 'e'
        and e.extname operator(pg_catalog.=) 'ai'
        and k.prokind in ('f', 'p')
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;
end
$func$;
