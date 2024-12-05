--FEATURE-FLAG: text_to_sql

-------------------------------------------------------------------------------
-- _set_description
create or replace function ai._set_description
( classid pg_catalog.oid
, objid pg_catalog.oid
, objsubid pg_catalog.int4
, description pg_catalog.text
) returns void
as $func$
    insert into ai.description
    ( objtype
    , objnames
    , objargs
    , classid
    , objid
    , objsubid
    , description
    )
    select
      x."type"
    , x.object_names
    , x.object_args
    , classid
    , objid
    , objsubid
    , _set_description.description
    from pg_catalog.pg_identify_object_as_address
    ( classid
    , objid
    , objsubid
    ) x
    on conflict on constraint description_pkey
    do update set description = _set_description.description
    ;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- set_table_description
create or replace function ai.set_table_description
( relation pg_catalog.regclass
, description pg_catalog.text
) returns void
as $func$
declare
    _classid pg_catalog.oid;
    _objid pg_catalog.oid;
    _objsubid pg_catalog.int4;
begin
    _classid = 'pg_catalog.pg_class'::pg_catalog.regclass::pg_catalog.oid;
    _objid = relation::pg_catalog.oid;
    _objsubid = 0;

    perform
    from pg_catalog.pg_class k
    where k.oid operator(pg_catalog.=) _objid
    and k.relkind in ('r', 'f', 'p')
    ;
    if not found then
        raise exception '% is not a table', relation::pg_catalog.text;
    end if;

    perform ai._set_description(_classid, _objid, _objsubid, description);
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- set_view_description
create or replace function ai.set_view_description
( relation pg_catalog.regclass
, description pg_catalog.text
) returns void
as $func$
declare
    _classid pg_catalog.oid;
    _objid pg_catalog.oid;
    _objsubid pg_catalog.int4;
begin
    _classid = 'pg_catalog.pg_class'::pg_catalog.regclass::pg_catalog.oid;
    _objid = relation::pg_catalog.oid;
    _objsubid = 0;

    perform
    from pg_catalog.pg_class k
    where k.oid operator(pg_catalog.=) _objid
    and k.relkind in ('v', 'm')
    ;
    if not found then
        raise exception '% is not a view', relation::pg_catalog.text;
    end if;

    perform ai._set_description(_classid, _objid, _objsubid, description);
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- set_column_description
create or replace function ai.set_column_description
( relation pg_catalog.regclass
, column_name pg_catalog.name
, description pg_catalog.text
) returns void
as $func$
declare
    _classid pg_catalog.oid;
    _objid pg_catalog.oid;
    _objsubid pg_catalog.int4;
begin
    _classid = 'pg_catalog.pg_class'::pg_catalog.regclass::pg_catalog.oid;
    _objid = relation::pg_catalog.oid;
    _objsubid = 0;

    select a.attnum into _objsubid
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_attribute a on (k.oid operator(pg_catalog.=) a.attrelid)
    where k.oid operator(pg_catalog.=) _objid
    and k.relkind in ('r', 'f', 'p', 'v', 'm')
    and a.attnum operator(pg_catalog.>) 0
    and a.attname operator(pg_catalog.=) column_name
    ;
    if not found then
        raise exception '% column not found', column_name;
    end if;

    perform ai._set_description(_classid, _objid, _objsubid, description);
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- set_function_description
create or replace function ai.set_function_description
( fn regprocedure
, description text
) returns void
as $func$
declare
    _classid pg_catalog.oid;
    _objid pg_catalog.oid;
    _objsubid pg_catalog.int4;
begin
    _classid = 'pg_catalog.pg_proc'::pg_catalog.regclass::pg_catalog.oid;
    _objid = fn::pg_catalog.oid;
    _objsubid = 0;

    perform ai._set_description(_classid, _objid, _objsubid, description);
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- _description_handle_drop
create or replace function ai._description_handle_drop()
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
        delete from ai.description
        where objtype operator(pg_catalog.=) _rec.object_type
        and objnames operator(pg_catalog.=) _rec.address_names
        and objargs operator(pg_catalog.=) _rec.address_args
        ;
        if _rec.object_type in ('table', 'view') then
            -- delete the columns too
            delete from ai.description
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
    where g.evtname operator(pg_catalog.=) '_description_handle_drop'
    and g.evtfoid operator(pg_catalog.=) pg_catalog.to_regproc('ai._description_handle_drop')
    ;
    if found then
        return;
    end if;

    create event trigger _description_handle_drop
    on sql_drop
    execute function ai._description_handle_drop();
end
$block$;

-------------------------------------------------------------------------------
-- _description_handle_ddl
create or replace function ai._description_handle_ddl()
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
        if _objtype = 'schema' then
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
                from ai.description d
                inner join pg_catalog.pg_class k on (d.objid operator(pg_catalog.=) k.oid)
                cross join lateral pg_catalog.pg_identify_object_as_address
                ( d.classid
                , d.objid
                , d.objsubid
                ) x
                where k.relnamespace operator(pg_catalog.=) _rec.objid
            )
            update ai.description as d set
              objtype = x.objtype
            , objnames = x.objnames
            , objargs = x.objargs
            from x
            where d.classid operator(pg_catalog.=) x.classid
            and d.objid operator(pg_catalog.=) x.objid
            and d.objsubid operator(pg_catalog.=) x.objsubid
            and (d.objtype, d.objnames, d.objargs) operator(pg_catalog.!=) (x.objtype, x.objnames, x.objargs) -- only if changed
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
                from ai.description d
                inner join pg_catalog.pg_proc f on (d.objid operator(pg_catalog.=) f.oid)
                cross join lateral pg_catalog.pg_identify_object_as_address
                ( d.classid
                , d.objid
                , d.objsubid
                ) x
                where f.pronamespace operator(pg_catalog.=) _rec.objid
            )
            update ai.description as d set
              objtype = x.objtype
            , objnames = x.objnames
            , objargs = x.objargs
            from x
            where d.classid operator(pg_catalog.=) x.classid
            and d.objid operator(pg_catalog.=) x.objid
            and d.objsubid operator(pg_catalog.=) x.objsubid
            and (d.objtype, d.objnames, d.objargs) operator(pg_catalog.!=) (x.objtype, x.objnames, x.objargs) -- only if changed
            ;

            return; -- done
        end if;

        -- alter table rename to
        -- alter view rename to
        -- alter function rename to
        -- alter table set schema
        -- alter view set schema
        -- alter function set schema
        update ai.description set
          objtype = _objtype
        , objnames = _objnames
        , objargs = _objargs
        where classid operator(pg_catalog.=) _rec.classid
        and objid operator(pg_catalog.=) _rec.objid
        and objsubid operator(pg_catalog.=) _rec.objsubid
        and (objtype, objnames, objargs) operator(pg_catalog.!=) (_objtype, _objnames, _objargs) -- only if changed
        ;
        if found and _objtype in ('table', 'view') then
            -- if table or view renamed or schema changed
            -- we need to update the columns too
            with a as
            (
                select
                  _rec.classid
                , a.attrelid as objid
                , a.attnum as objsubid
                from pg_catalog.pg_attribute a
                where a.attrelid operator(pg_catalog.=) _rec.objid
                and a.attnum operator(pg_catalog.>) 0
            )
            , x as
            (
                select
                  a.classid
                , a.objid
                , a.objsubid
                , x."type" as objtype
                , x.object_names as objnames
                , x.object_args as objargs
                from a
                cross join lateral pg_catalog.pg_identify_object_as_address
                ( a.classid
                , a.objid
                , a.objsubid
                ) x
            )
            update ai.description d set
              objtype = x.objtype
            , objnames = x.objnames
            , objargs = x.objargs
            from x
            where d.classid operator(pg_catalog.=) x.classid
            and d.objid operator(pg_catalog.=) x.objid
            and d.objsubid operator(pg_catalog.=) x.objsubid
            and (d.objtype, d.objnames, d.objargs) operator(pg_catalog.!=) (x.objtype, x.objnames, x.objargs) -- only if changed
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
    where g.evtname operator(pg_catalog.=) '_description_handle_ddl'
    and g.evtfoid operator(pg_catalog.=) pg_catalog.to_regproc('ai._description_handle_ddl')
    ;
    if found then
        return;
    end if;

    create event trigger _description_handle_ddl
    on ddl_command_end
    execute function ai._description_handle_ddl();
end
$block$;

-------------------------------------------------------------------------------
-- post_restore
create or replace function ai.post_restore() returns void
as $func$
declare
    _sql text;
begin
    -- disable vectorizer triggers on the ai.description table
    for _sql in
    (
        select pg_catalog.format
        ( $sql$alter table ai.description disable trigger %I$sql$
        , g.tgname
        )
        from pg_catalog.pg_trigger g
        where g.tgrelid operator(pg_catalog.=) 'ai.description'::pg_catalog.regclass::pg_catalog.oid
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
            from ai.description d
            where d.objtype not in ('view column', 'materialized view column')
        ) d
        cross join lateral pg_catalog.pg_get_object_address
        ( d.objtype
        , d.objnames
        , d.objargs
        ) x
    )
    update ai.description as d set
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
        from ai.description d
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
    update ai.description as d set
      classid = y.classid
    , objid = y.objid
    , objsubid = y.objsubid
    from y
    where d.objtype operator(pg_catalog.=) y.objtype
    and d.objnames operator(pg_catalog.=) y.objnames
    and d.objargs operator(pg_catalog.=) y.objargs
    and (d.classid, d.objid, d.objsubid) operator(pg_catalog.!=) (y.classid, y.objid, y.objsubid) -- noop if nothing to change
    ;

    -- re-enable vectorizer triggers on the ai.description table
    for _sql in
    (
        select pg_catalog.format
        ( $sql$alter table ai.description enable trigger %I$sql$
        , g.tgname
        )
        from pg_catalog.pg_trigger g
        where g.tgrelid operator(pg_catalog.=) 'ai.description'::pg_catalog.regclass::pg_catalog.oid
        and g.tgname like '_vectorizer_src_trg_%'
    )
    loop
        execute _sql;
    end loop;
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;
