
-- look for tables in the postgres_air schema at generate descriptions
select
  format('select x.sql from ai.generate_description(%L) x;', x.oid::regclass)
, format('select x.sql from ai.generate_column_descriptions(%L) x;', x.oid::regclass)
from
(
    select k.*
    from pg_class k
    inner join pg_namespace n on (k.relnamespace = n.oid)
    where n.nspname = 'postgres_air'
    and k.relkind in ('r', 'p', 'v', 'm')
    order by k.relname
) x
\gexec
