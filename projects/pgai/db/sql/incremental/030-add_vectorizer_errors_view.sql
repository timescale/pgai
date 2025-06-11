-- rename the ai.vectorizer_errors table to ai._vectorizer_errors
alter table ai.vectorizer_errors rename to _vectorizer_errors;

-- rename the existing index on the ai.vectorizer_error so it follows the right naming convention (adds the _ prefix)
-- this is not strictly necessary, but it is a good practice to keep the naming consistent
alter index ai.vectorizer_errors_id_recorded_idx rename to _vectorizer_errors_id_recorded_idx;

-- create a view including vectorizer name
create or replace view ai.vectorizer_errors as
select 
  ve.*,
  v.name
from
  ai._vectorizer_errors ve
  left join ai.vectorizer v on ve.id = v.id;


-- grant privileges on new ai.vectorizer_errors view
do language plpgsql $block$
declare
    _sql text;
begin
    for _sql in
    (
        -- generate grant commands with SELECT privilege
        select format
        ( $$GRANT SELECT ON ai.vectorizer_errors TO %I%s$$
        , grantee.rolname
        , case when x.is_grantable then ' WITH GRANT OPTION'
          else ''
          end
        )
        from pg_class k
        inner join pg_namespace n on (k.relnamespace = n.oid)
        cross join lateral aclexplode(k.relacl) x
        inner join pg_roles grantee on (grantee.oid = x.grantee)
        where n.nspname = 'ai'
        and k.relname = '_vectorizer_errors' -- copy grants from the old table
        and x.privilege_type = 'SELECT' -- only SELECT privileges, no need others
        and not has_table_privilege -- only grant users with no privileges by default
          ( grantee.oid
          , 'ai.vectorizer_errors'::regclass::oid -- the view
          , case when x.is_grantable then 'SELECT WITH GRANT OPTION'
          else 'SELECT'
          end
          )
    )
    loop
        execute _sql;
    end loop;
end
$block$;