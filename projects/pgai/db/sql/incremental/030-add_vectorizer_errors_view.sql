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


-- grant privileges on vectorizer_errors
DO $$
DECLARE
    to_user text;
    priv_type text;
    with_grant text;
    rec RECORD;
BEGIN
    -- find all users that have permissions on ai.vectorizer table and grant them to the errors ones
    FOR rec IN 
        SELECT DISTINCT grantee as username
        FROM information_schema.role_table_grants
        WHERE table_schema = 'ai' 
        AND table_name = '_vectorizer_errors'
    LOOP
        to_user := rec.username;
        priv_type := rec.privilege_type
        with_grant = ''
        if rec.is_grantable then
           with_grant = ' WITH GRANT OPTION';
        end if;
        EXECUTE format('GRANT %I ON ai.vectorizer_errors TO %I %s', priv_type, to_user, with_grant);
    END LOOP;
END
$$; 