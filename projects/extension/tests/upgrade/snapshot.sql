-- display the contents of the extension
\dx+ ai

DO $$
declare
    _tablename text;
    _functionname text;
begin
    --drop all tables in the ai schema that are not in the extension
    for _tablename in
    select tablename
    from pg_tables
    where schemaname = 'ai'
      and tablename not in (
      select
        k.relname
      from pg_catalog.pg_depend d
      inner join pg_catalog.pg_class k on (d.objid = k.oid)
      inner join pg_catalog.pg_namespace n on (k.relnamespace = n.oid)
      inner join pg_catalog.pg_extension x on (d.refobjid = x.oid)
      where d.classid = 'pg_catalog.pg_class'::regclass::oid
        and d.refclassid = 'pg_catalog.pg_extension'::regclass::oid
        and d.deptype = 'e'
        and x.extname = 'ai'
      ) 
    loop
        execute 'drop table if exists ai.' || _tablename || ' cascade;';
    end loop;
    
    --drop all functions in the ai schema that are not in the extension
    for _functionname in
    select format
    ( $sql$DROP %s IF EXISTS %I(%s)$sql$
    , case when p.prokind = 'f' then 'FUNCTION' else 'PROCEDURE' end
    , p.proname
    , pg_catalog.pg_get_function_identity_arguments(p.oid)
    )
    from pg_catalog.pg_proc p
    inner join pg_catalog.pg_namespace n on (p.pronamespace = n.oid)
    where n.nspname = 'ai'
      and p.proname not in (
        select
          p.proname
        from pg_catalog.pg_depend d
        inner join pg_catalog.pg_proc p on (d.objid = p.oid)
        inner join pg_catalog.pg_namespace n on (p.pronamespace = n.oid)
        inner join pg_catalog.pg_extension x on (d.refobjid = x.oid)
        where d.classid = 'pg_catalog.pg_proc'::regclass::oid
          and d.refclassid = 'pg_catalog.pg_extension'::regclass::oid
          and d.deptype = 'e'
          and x.extname = 'ai'
      )
    loop
        execute _functionname;
    end loop;
end $$;

-- verbose display of the objects in the ai schema
\d+ ai.*

-- the contents of the migration table
select
  "name"
, case "name"
    -- we hacked this frozen file and thus must make an exception for it
    when '002-secret_permissions.sql' then '066cbcf6e6898c241a665b08ee25b4cb'
    --this file changed during divesting 
    when '009-drop-truncate-from-vectorizer-config.sql' then 'skip'
    else md5(convert_to(body, 'UTF8'))
  end as body_md5
from ai.migration
where name not in (
  '001-vectorizer.sql',
 '003-vec-storage.sql', 
 '005-vectorizer-queue-pending.sql', 
 '006-drop-vectorizer.sql', 
 '012-add-vectorizer-disabled-column.sql',
 '017-upgrade-source-pk.sql',
 '018-drop-foreign-key-constraint.sql')
order by applied_at
;

-- the contents of the _secret_permissions table
select *
from ai._secret_permissions
;

\d+ wiki.*
