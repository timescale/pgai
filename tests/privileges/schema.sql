\set users {bob,fred,alice,jill}

-- check schema privileges
\! rm -f schema.actual
select
  n as "schema"
, u as "user"
, p as "privilege"
, case has_schema_privilege(u, n, p) when true then 'YES' else 'no' end as granted
from unnest(:'users'::text[]) u
cross join unnest(array['ai', 'wiki']) n
cross join unnest(array['create', 'usage']) p
order by n, p, u
\g (format=aligned) schema.actual
