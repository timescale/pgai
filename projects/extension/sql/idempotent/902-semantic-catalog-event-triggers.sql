--FEATURE-FLAG: text_to_sql

-------------------------------------------------------------------------------
-- _semantic_catalog_obj_handle_drop
create or replace function ai._semantic_catalog_obj_handle_drop()
returns event_trigger as
$func$
declare
    _rec record;
begin
    -- this function is security definer
    -- fully-qualify everything and be careful of security holes
    for _rec in
    (
        select
          d.classid
        , d.objid
        , d.objsubid
        --, d.original
        --, d.normal
        --, d.is_temporary
        , d.object_type
        --, d.schema_name
        --, d.object_name
        --, d.object_identity
        , d.address_names
        , d.address_args
        from pg_catalog.pg_event_trigger_dropped_objects() d
    )
    loop
        delete from ai.semantic_catalog_obj
        where objtype operator(pg_catalog.=) _rec.object_type
        and objnames operator(pg_catalog.=) _rec.address_names
        and objargs operator(pg_catalog.=) _rec.address_args
        ;
        if _rec.object_type in ('table', 'view') then
            -- delete the columns too
            delete from ai.semantic_catalog_obj
            where classid operator(pg_catalog.=) _rec.classid
            and objid operator(pg_catalog.=) _rec.objid
            ;
        end if;
    end loop;
end;
$func$
language plpgsql volatile security definer -- definer on purpose!
set search_path to pg_catalog, pg_temp
;

-- install the event trigger if not exists
do language plpgsql $block$
begin
    -- if the event trigger already exists, noop
    perform
    from pg_catalog.pg_event_trigger g
    where g.evtname operator(pg_catalog.=) '_semantic_catalog_obj_handle_drop'
    and g.evtfoid operator(pg_catalog.=) pg_catalog.to_regproc('ai._semantic_catalog_obj_handle_drop')
    ;
    if found then
        return;
    end if;

    create event trigger _semantic_catalog_obj_handle_drop
    on sql_drop
    execute function ai._semantic_catalog_obj_handle_drop();
end
$block$;

-------------------------------------------------------------------------------
-- _semantic_catalog_obj_handle_ddl
create or replace function ai._semantic_catalog_obj_handle_ddl()
returns event_trigger as
$func$
declare
    _rec record;
    _objtype pg_catalog.text;
    _objnames pg_catalog.text[];
    _objargs pg_catalog.text[];
begin
    -- this function is security definer
    -- fully-qualify everything and be careful of security holes
    for _rec in
    (
        select
          d.classid
        , d.objid
        , d.objsubid
        , d.command_tag
        --, d.object_type
        --, d.schema_name
        --, d.object_identity
        --, d.in_extension
        --, d.command
        from pg_catalog.pg_event_trigger_ddl_commands() d
    )
    loop
        select
          x."type"
        , x.object_names
        , x.object_args
        into strict
          _objtype
        , _objnames
        , _objargs
        from pg_catalog.pg_identify_object_as_address
        ( _rec.classid
        , _rec.objid
        , _rec.objsubid
        ) x;

        -- alter schema rename to
        if _objtype operator(pg_catalog.=) 'schema' then
            -- tables/views/columns
            with x as
            (
                select
                  d.classid
                , d.objid
                , d.objsubid
                , x."type" as objtype
                , x.object_names as objnames
                , x.object_args as objargs
                from ai.semantic_catalog_obj d
                inner join pg_catalog.pg_class k on (d.objid operator(pg_catalog.=) k.oid)
                cross join lateral pg_catalog.pg_identify_object_as_address
                ( d.classid
                , d.objid
                , d.objsubid
                ) x
                where k.relnamespace operator(pg_catalog.=) _rec.objid
            )
            update ai.semantic_catalog_obj as d set
              objnames = x.objnames
            from x
            where d.classid operator(pg_catalog.=) x.classid
            and d.objid operator(pg_catalog.=) x.objid
            and d.objsubid operator(pg_catalog.=) x.objsubid
            and d.objnames operator(pg_catalog.!=) x.objnames -- only if changed
            ;

            -- functions
            with x as
            (
                select
                  d.classid
                , d.objid
                , d.objsubid
                , x."type" as objtype
                , x.object_names as objnames
                , x.object_args as objargs
                from ai.semantic_catalog_obj d
                inner join pg_catalog.pg_proc f on (d.objid operator(pg_catalog.=) f.oid)
                cross join lateral pg_catalog.pg_identify_object_as_address
                ( d.classid
                , d.objid
                , d.objsubid
                ) x
                where f.pronamespace operator(pg_catalog.=) _rec.objid
            )
            update ai.semantic_catalog_obj as d set
              objnames = x.objnames
            from x
            where d.classid operator(pg_catalog.=) x.classid
            and d.objid operator(pg_catalog.=) x.objid
            and d.objsubid operator(pg_catalog.=) x.objsubid
            and d.objnames operator(pg_catalog.!=) x.objnames -- only if changed
            ;

            return; -- done
        end if;

        -- alter table rename to
        -- alter view rename to
        -- alter function rename to
        -- alter table set schema
        -- alter view set schema
        -- alter function set schema
        update ai.semantic_catalog_obj set
          objnames = _objnames
        , objargs = _objargs
        where classid operator(pg_catalog.=) _rec.classid
        and objid operator(pg_catalog.=) _rec.objid
        and objsubid operator(pg_catalog.=) _rec.objsubid
        and (objnames, objargs) operator(pg_catalog.!=) (_objnames, _objargs) -- only if changed
        ;
        if found and _objtype in ('table', 'view') then
            -- if table or view renamed or schema changed
            -- we need to update the columns too
            with attr as
            (
                select
                  _rec.classid
                , a.attrelid as objid
                , a.attnum as objsubid
                from pg_catalog.pg_attribute a
                where a.attrelid operator(pg_catalog.=) _rec.objid
                and a.attnum operator(pg_catalog.>) 0
                and not a.attisdropped
            )
            , xref as
            (
                select
                  attr.classid
                , attr.objid
                , attr.objsubid
                , x."type" as objtype
                , x.object_names as objnames
                , x.object_args as objargs
                from attr
                cross join lateral pg_catalog.pg_identify_object_as_address
                ( attr.classid
                , attr.objid
                , attr.objsubid
                ) x
            )
            update ai.semantic_catalog_obj d set
              objnames = xref.objnames
            , objargs = xref.objargs
            from xref
            where d.classid operator(pg_catalog.=) xref.classid
            and d.objid operator(pg_catalog.=) xref.objid
            and d.objsubid operator(pg_catalog.=) xref.objsubid
            and (d.objnames, d.objargs) operator(pg_catalog.!=) (xref.objnames, xref.objargs) -- only if changed
            ;
        end if;
    end loop;
end
$func$
language plpgsql volatile security definer -- definer on purpose!
set search_path to pg_catalog, pg_temp
;

-- install the event trigger if not exists
do language plpgsql $block$
begin
    -- if the event trigger already exists, noop
    perform
    from pg_catalog.pg_event_trigger g
    where g.evtname operator(pg_catalog.=) '_semantic_catalog_obj_handle_ddl'
    and g.evtfoid operator(pg_catalog.=) pg_catalog.to_regproc('ai._semantic_catalog_obj_handle_ddl')
    ;
    if found then
        return;
    end if;

    create event trigger _semantic_catalog_obj_handle_ddl
    on ddl_command_end
    execute function ai._semantic_catalog_obj_handle_ddl();
end
$block$;
