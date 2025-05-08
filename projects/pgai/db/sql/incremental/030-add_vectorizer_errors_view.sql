-- rename the ai.vectorizer_errors table to ai._vectorizer_errors
alter table ai.vectorizer_errors rename to _vectorizer_errors;

-- drop any existing indexes on the old table that would have been associated with the (id, recorded) columns
-- this is for index naming consistency purpose, not strictly necessary
do $$
declare
  _index_name text;
begin
  select indexname into _index_name
  from pg_indexes
  where schemaname = 'ai' 
    and tablename = 'vectorizer_errors'
    and indexdef like '%id, recorded%';
    
  if _index_name is not null then
    execute 'drop index if exists ai.' || quote_ident(_index_name);
  end if;
end
$$;

-- recreate the previous index to perform lookups by vectorizer id
create index on ai._vectorizer_errors (id, recorded);

-- create a view including vectorizer name
create or replace view ai.vectorizer_errors as
select 
  ve.*,
  v.name
from
  ai._vectorizer_errors ve
  join ai.vectorizer v on ve.id = v.id;


-- grant privileges on _vectorizer_errors and vectorizer_errors to vectorizer users
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