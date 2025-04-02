
do language plpgsql $block$
declare
    _vec ai.vectorizer;
    _source pg_catalog.oid;
    _source_pk pg_catalog.jsonb;
begin
    for _vec in (select * from ai.vectorizer)
    loop
        _source = pg_catalog.to_regclass(pg_catalog.format('%I.%I', _vec.source_schema, _vec.source_table));
        if _source is null then
            continue;
        end if;
        
        select pg_catalog.jsonb_agg(x) into _source_pk
        from
        (
            select e.attnum, e.pknum, a.attname, pg_catalog.format_type(y.oid, a.atttypmod) as typname
            from pg_catalog.pg_constraint k
            cross join lateral pg_catalog.unnest(k.conkey) with ordinality e(attnum, pknum)
            inner join pg_catalog.pg_attribute a
                on (k.conrelid operator(pg_catalog.=) a.attrelid
                    and e.attnum operator(pg_catalog.=) a.attnum)
            inner join pg_catalog.pg_type y on (a.atttypid operator(pg_catalog.=) y.oid)
            where k.conrelid operator(pg_catalog.=) _source
            and k.contype operator(pg_catalog.=) 'p'
        ) x;
        
        if _source_pk is null then
            continue;
        end if;
        
        update ai.vectorizer u set source_pk = _source_pk
        where u.id = _vec.id
        ;
    end loop;
end;
$block$;
