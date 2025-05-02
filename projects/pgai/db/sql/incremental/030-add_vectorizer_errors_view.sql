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
