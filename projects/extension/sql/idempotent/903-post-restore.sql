--FEATURE-FLAG: text_to_sql

-------------------------------------------------------------------------------
-- post_restore
create or replace function ai.post_restore() returns void
as $func$
declare
    _sql text;
begin
    -- disable vectorizer triggers on the ai.semantic_catalog_obj table
    for _sql in
    (
        select pg_catalog.format
        ( $sql$alter table ai.semantic_catalog_obj disable trigger %I$sql$
        , g.tgname
        )
        from pg_catalog.pg_trigger g
        where g.tgrelid operator(pg_catalog.=) 'ai.semantic_catalog_obj'::pg_catalog.regclass::pg_catalog.oid
        and g.tgname like '_vectorizer_src_trg_%'
    )
    loop
        execute _sql;
    end loop;

    -- oids are likely invalid after a dump/restore
    -- look up the new oids and true up
    with x as
    (
        select
          d.objtype
        , d.objnames
        , d.objargs
        , x.classid
        , x.objid
        , x.objsubid
        from
        (
            -- despite what the docs say, pg_get_object_address does NOT support everything that pg_identify_object_as_address does
            -- view columns and materialized view columns will throw an error
            -- https://github.com/postgres/postgres/blob/master/src/backend/catalog/objectaddress.c#L695
            select *
            from ai.semantic_catalog_obj d
            where d.objtype not in ('view column', 'materialized view column')
        ) d
        cross join lateral pg_catalog.pg_get_object_address
        ( d.objtype
        , d.objnames
        , d.objargs
        ) x
    )
    update ai.semantic_catalog_obj as d set
      classid = x.classid
    , objid = x.objid
    , objsubid = x.objsubid
    from x
    where d.objtype operator(pg_catalog.=) x.objtype
    and d.objnames operator(pg_catalog.=) x.objnames
    and d.objargs operator(pg_catalog.=) x.objargs
    and (d.classid, d.objid, d.objsubid) operator(pg_catalog.!=) (x.classid, x.objid, x.objsubid) -- noop if nothing to change
    ;

    -- deal with view columns and materialized view columns
    with x as
    (
        select
          pg_catalog.to_regclass(pg_catalog.array_to_string(pg_catalog.trim_array(d.objnames, 1), '.')) as attrelid
        , d.objnames[3] as attname
        , d.objtype
        , d.objnames
        , d.objargs
        from ai.semantic_catalog_obj d
        where d.objtype in ('view column', 'materialized view column')
        and pg_catalog.array_length(d.objnames, 1) operator(pg_catalog.=) 3
    )
    , y as
    (
        select
          'pg_catalog.pg_class'::pg_catalog.regclass::pg_catalog.oid as classid
        , a.attrelid as objid
        , a.attnum as objsubid
        , x.objtype
        , x.objnames
        , x.objargs
        from x
        inner join pg_catalog.pg_attribute a
        on (x.attrelid::pg_catalog.oid operator(pg_catalog.=) a.attrelid and x.attname operator(pg_catalog.=) a.attname)
        where x.attrelid is not null
    )
    update ai.semantic_catalog_obj as d set
      classid = y.classid
    , objid = y.objid
    , objsubid = y.objsubid
    from y
    where d.objtype operator(pg_catalog.=) y.objtype
    and d.objnames operator(pg_catalog.=) y.objnames
    and d.objargs operator(pg_catalog.=) y.objargs
    and (d.classid, d.objid, d.objsubid) operator(pg_catalog.!=) (y.classid, y.objid, y.objsubid) -- noop if nothing to change
    ;

    -- re-enable vectorizer triggers on the ai.semantic_catalog_obj table
    for _sql in
    (
        select pg_catalog.format
        ( $sql$alter table ai.semantic_catalog_obj enable trigger %I$sql$
        , g.tgname
        )
        from pg_catalog.pg_trigger g
        where g.tgrelid operator(pg_catalog.=) 'ai.semantic_catalog_obj'::pg_catalog.regclass::pg_catalog.oid
        and g.tgname like '_vectorizer_src_trg_%'
    )
    loop
        execute _sql;
    end loop;
end;
$func$ language plpgsql volatile security definer -- definer on purpose
set search_path to pg_catalog, pg_temp
;
