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
    to_user text;
    priv_type text;
    with_grant text;
    rec record;
begin
    -- find all users that have permissions on old ai.vectorizer_errors table and grant them to the view
    for rec in
        select distinct grantee as username, privilege_type, is_grantable
        from information_schema.role_table_grants
        where table_schema = 'ai'
        and table_name = '_vectorizer_errors'
    loop
        to_user := rec.username;
        priv_type := rec.privilege_type;
        with_grant := '';
        if rec.is_grantable then
           with_grant := ' WITH GRANT OPTION';
        end if;
        execute format('GRANT %s ON ai.vectorizer_errors TO %I %s', priv_type, to_user, with_grant);
    end loop;
end
$block$;