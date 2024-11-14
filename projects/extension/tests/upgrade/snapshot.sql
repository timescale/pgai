-- display the contents of the extension
\dx+ ai

-- verbose display of the objects in the ai schema
\d+ ai.*

-- the contents of the migration table
select "name", md5(convert_to(body, 'UTF8')) as body_md5
from ai.migration
order by applied_at
;

-- the contents of the _secret_permissions table
select *
from ai._secret_permissions
;

select
  id
, source_schema
, source_table
, source_pk
, target_schema
, target_table
, view_schema
, view_name
, trigger_name
, queue_schema
, queue_table
, config - 'version' as config
from ai.vectorizer
;

\d+ wiki.*
