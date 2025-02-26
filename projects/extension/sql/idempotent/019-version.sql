
-------------------------------------------------------------------------------
-- version
create or replace function ai.version(out version text, out git_sha text)
as $sql$
    select
      '@extversion@'
    , '@gitsha@'
$sql$
language sql immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;
