
-- make sure tables and sequences are pg_dump'ed properly
do $block$
declare
    _sql text;
begin
    for _sql in
    (
        -- find tables and sequences which belong to the extension so we can mark them to have
        -- their data dumped by pg_dump
        select format
        ( $$select pg_catalog.pg_extension_config_dump('%I.%I'::pg_catalog.regclass, '')$$
        , n.nspname
        , k.relname
        )
        from pg_catalog.pg_depend d
        inner join pg_catalog.pg_extension e on (d.refobjid = e.oid)
        inner join pg_catalog.pg_class k on (d.objid = k.oid)
        inner join pg_namespace n on (k.relnamespace = n.oid)
        where d.refclassid operator(pg_catalog.=) 'pg_catalog.pg_extension'::pg_catalog.regclass
        and d.deptype operator(pg_catalog.=) 'e'
        and e.extname operator(pg_catalog.=) 'ai'
        and k.relkind in ('r', 'p', 'S') -- tables and sequences
        order by n.nspname, k.relname
    )
    loop
        execute _sql;
    end loop;
end;
$block$;
