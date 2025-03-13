-- display the contents of the extension
\set ON_ERROR_STOP 0
\dx+ ai

-- verbose display of the objects in the ai schema
\d+ ai.*
--todo: add function source
\df ai.*



-- the contents of the migration table
select
  "name"
, case "name"
    -- we hacked this frozen file and thus must make an exception for it
    when '002-secret_permissions.sql' then '066cbcf6e6898c241a665b08ee25b4cb'
    else md5(convert_to(body, 'UTF8'))
  end as body_md5
from ai.migration_app
order by applied_at
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
