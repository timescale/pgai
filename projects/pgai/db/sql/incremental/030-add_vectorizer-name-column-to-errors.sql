-- add the column `name` to the `ai.vectorizer_errors` table
-- which will be used to store the name of the vectorizer
alter table ai.vectorizer_errors
add column name name check (name ~ '^[a-z][a-z_0-9]*$');

-- add a new index to perform lookups by vectorizer name
create index on ai.vectorizer_errors (name, recorded);

-- populate the new column with each vectorizer name
update ai.vectorizer_errors ve
set name = v.name
from ai.vectorizer v
where ve.id = v.id;
