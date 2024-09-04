\set users {bob,fred,alice,jill}

-- check schema privileges
\! rm -f schema.actual
select
  n as "schema"
, u as "user"
, p as "privilege"
, has_schema_privilege(u, n, p) as granted
from unnest(:'users'::text[]) u
cross join unnest(array['ai', 'wiki']) n
cross join unnest(array['create', 'usage']) p
order by n, p, u
\g (format=aligned) schema.actual
