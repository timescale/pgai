-- display the contents of the extension
\set ON_ERROR_STOP 0

-- verbose display of the objects in the ai schema
\d+ ai.*

\df+ ai.*
SELECT
  proname AS function_name,
  pg_get_functiondef(p.oid) AS body
FROM
  pg_proc p
JOIN
  pg_namespace n ON n.oid = p.pronamespace
WHERE
  n.nspname = 'ai'
ORDER BY
  proname, body;

\z ai.*
\dt+ ai.*
\dv+ ai.*
\di+ ai.*
\dy+ ai.*



-- the contents of the migration table
select
  "name"
, case "name"
    -- this file had pg_catalog.pg_extension_config_dump commands so we had to modify it
    when '001-vectorizer.sql' then 'skip'
    -- this file had both vectorizer and non-vectorizer code so we had to modify it
    when '009-drop-truncate-from-vectorizer-config.sql' then 'skip'
    else md5(convert_to(body, 'UTF8'))
  end as body_md5
from ai.pgai_lib_migration
order by applied_at
;

select
  id
, source_schema
, source_table
, source_pk
, trigger_name
, queue_schema
, queue_table
, config - 'version' as config
from ai.vectorizer
;

\d+ wiki.*
\z wiki.*
\dt+ wiki.*
\dv+ wiki.*
\di+ wiki.*
\dy+ wiki.*
