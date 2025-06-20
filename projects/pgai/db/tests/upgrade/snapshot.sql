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
\dy+

-- Check pgai library version
SELECT name, version FROM ai.pgai_lib_version;

-- the contents of the migration table
select
  "name",
  md5(convert_to(replace(body, :'source_version', :'target_version'), 'UTF8')) as body_md5
from ai.pgai_lib_migration
where (:exclude_list) is null or name not in (:exclude_list)
order by applied_at;

-- the contents of the wiki schema
\d+ wiki.*
\z wiki.*
\dt+ wiki.*
\dv+ wiki.*
\di+ wiki.*