
-- switch the vector columns from storage external to storage main
do language plpgsql $block$
declare
    _sql pg_catalog.text;
begin
    for _sql in
    (
        select pg_catalog.format
        ( $sql$alter table %I.%I alter column embedding set storage main$sql$
        , v.target_schema
        , v.target_table
        )
        from ai.vectorizer v
        inner join pg_catalog.pg_class k on (k.relname operator(pg_catalog.=) v.target_table)
        inner join pg_catalog.pg_namespace n
            on (k.relnamespace operator(pg_catalog.=) n.oid and n.nspname operator(pg_catalog.=) v.target_schema)
        inner join pg_catalog.pg_attribute a on (k.oid operator(pg_catalog.=) a.attrelid)
        where a.attname operator(pg_catalog.=) 'embedding'
        and a.attstorage not in ('m', 'p') -- not main or plain
    )
    loop
        raise info '%', _sql;
        execute _sql;
    end loop;
end;
$block$;
