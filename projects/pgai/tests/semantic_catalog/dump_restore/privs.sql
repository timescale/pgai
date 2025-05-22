-- check table privileges
select
  n.nspname as "schema"
, k.relname as "table"
, u as "user"
, p as "privilege"
, case has_table_privilege(u, k.oid, p) when true then 'YES' else 'no' end as granted
from unnest('{ada,vera,edith}'::text[]) u
inner join pg_namespace n on (n.nspname = any(array['ai', 'postgres_air']))
inner join pg_class k on (n.oid = k.relnamespace and k.relkind in ('r', 'p'))
cross join unnest(array['select', 'insert', 'update', 'delete']) p
where k.relname like 'semantic_catalog%'
order by n.nspname, k.relname, u, p
;
-- check sequence privileges
select
  n.nspname as "schema"
, k.relname as "sequence"
, u as "user"
, p as "privilege"
, case has_sequence_privilege(u, k.oid, p) when true then 'YES' else 'no' end as granted
from unnest('{ada,vera,edith}'::text[]) u
inner join pg_namespace n on (n.nspname = any(array['ai', 'postgres_air']))
inner join pg_class k on (n.oid = k.relnamespace and k.relkind in ('S'))
cross join unnest(array['select', 'update', 'usage']) p
where k.relname like 'semantic_catalog%'
order by n.nspname, k.relname, u, p
;
