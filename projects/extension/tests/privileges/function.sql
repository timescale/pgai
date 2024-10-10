\set users {bob,fred,alice,jill}

-- check function privileges
\! rm -f function.actual
select
  f.prokind
, u as "user"
, p as "privilege"
, case has_function_privilege(u, f.oid, p) when true then 'YES' else 'no' end as granted
, n.nspname as "schema"
, format('%s(%s)', f.proname, pg_get_function_identity_arguments(f.oid)) as func
from unnest(:'users'::text[]) u
inner join pg_namespace n on (n.nspname = any(array['ai']))
inner join pg_proc f on (n.oid = f.pronamespace)
cross join unnest(array['execute']) p
order by n.nspname, 6, p, u
\g (format=aligned) function.actual
