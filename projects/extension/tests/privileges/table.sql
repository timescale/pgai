\set users {bob,fred,alice,jill}

-- check table privileges
\! rm -f schema.actual
select
  n.nspname as "schema"
, k.relname as "table"
, u as "user"
, p as "privilege"
, case has_table_privilege(u, k.oid, p) when true then 'YES' else 'no' end as granted
from unnest(:'users'::text[]) u
inner join pg_namespace n on (n.nspname = any(array['ai', 'wiki']))
inner join pg_class k on (n.oid = k.relnamespace and k.relkind in ('r', 'p'))
cross join unnest(array['select', 'insert', 'update', 'delete']) p
order by n.nspname, k.relname, u, p
\g (format=aligned) table.actual
