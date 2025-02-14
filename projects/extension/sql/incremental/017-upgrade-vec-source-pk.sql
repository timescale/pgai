
do language plpgsql $block$
declare
    _vec ai.vectorizer;
    _version text;
    _parts text[];
    _source_pk jsonb;
    _source regclass;
begin
    -- loop over all vectorizers
    for _vec in (select * from ai.vectorizer)
    loop
        -- if the vectorizer was created at or before 0.8.0 we need to upgrade it
        -- this version check is likely not necessary since this is an incremental migration
        -- but i'm being extra paranoid
        _version = _vec.config operator(pg_catalog.->>) 'version';
        _parts = regexp_split_to_array(_version, '[.\-]');
        if _parts[1]::int4 > 0 then -- major
            continue;
        end if;
        if _parts[2]::int4 > 8 then -- minor
            continue;
        end if;
        if _parts[2]::int4 = 8 and _parts[3]::int4 > 0 then -- patch
            continue;
        end if;
        
        -- look up the source table
        _source = pg_catalog.to_regclass
        ( pg_catalog.format
          ( '%I.%I'
          , _vec.source_schema
          , _vec.source_table
          )
        );
        if _source is null then
            continue;
        end if;
        
        -- reconstruct the primary key info with the fix for typname
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
        ) x
        ;
        if _source_pk is null then
            continue;
        end if;
        
        -- update the row
        update ai.vectorizer v set source_pk = _source_pk
        where v.id = _vec.id
        ;
    end loop;
end;
$block$;
