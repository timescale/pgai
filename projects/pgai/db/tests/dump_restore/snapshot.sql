\pset pager off

select version();

-- Lists schemas
\dn+
-- Lists installed extensions.
\dx
-- Lists default access privilege settings.
\ddp

-- dynamically generate meta commands to describe schemas
\! rm -f describe_schemas.sql
select format('%s %s', c.c, s.s)
from unnest(array
[ 'public'
, 'ai'
]) s(s)
cross join unnest(array
[ '\dp+' -- Lists tables, views and sequences with their associated access privileges
, '\ddp' -- Lists default access privilege settings. An entry is shown for each role (and schema, if applicable) for which the default privilege settings have been changed from the built-in defaults.
]) c(c)
order by c.c, s.s
\g (tuples_only=on format=csv) describe_schemas.sql
\i describe_schemas.sql

-- dynamically generate meta commands to describe objects in the schemas
\! rm -f describe_objects.sql
select format('%s %s', c.c, s.s)
from unnest(array
[ 'public.*'
, 'ai.*'
]) s(s)
cross join unnest(array
[ '\d+' -- Describe each relation
, '\df+' -- Describe functions
, '\dp+' -- Lists tables, views and sequences with their associated access privileges.
, '\di' -- Describe indexes
, '\do' -- Lists operators with their operand and result types
, '\dT' -- Lists data types.
]) c(c)
order by c.c, s.s
\g (tuples_only=on format=csv) describe_objects.sql
\i describe_objects.sql

-- snapshot the data from all the tables and views
select
    format($$select '%I.%I' as table_snapshot;$$, n.nspname, k.relname),
    case
        -- we don't care about comparing the applied_at_version and applied_at columns of the migration table
        when n.nspname = 'ai'::name and k.relname = 'migration'::name
            then 'select name, body from ai.migration order by name, body;'
        else format('select * from %I.%I tbl order by tbl;', n.nspname, k.relname)
    end
from pg_namespace n
inner join pg_class k on (n.oid = k.relnamespace)
where k.relkind in ('r', 'p', 'v')
and n.nspname in
( 'public'
, 'ai'
)
order by n.nspname, k.relname
\gexec
