--FEATURE-FLAG: text_to_sql

-------------------------------------------------------------------------------
-- add_sql_example
create or replace function ai.add_sql_example
( sql pg_catalog.text
, description pg_catalog.text
) returns int
as $func$
    insert into ai.semantic_catalog_sql (sql, description)
    values (trim(sql), trim(description))
    returning id
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- _set_description
create or replace function ai._set_description
( classid pg_catalog.oid
, objid pg_catalog.oid
, objsubid pg_catalog.int4
, description pg_catalog.text
) returns void
as $func$
    insert into ai.semantic_catalog_obj
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
    on conflict (objtype, objnames, objargs)
    do update set description = _set_description.description
    ;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- set_description
create or replace function ai.set_description
( relation pg_catalog.regclass
, description pg_catalog.text
) returns void
as $func$
declare
    _classid pg_catalog.oid;
    _objid pg_catalog.oid;
    _objsubid pg_catalog.int4;
    _relkind pg_catalog."char";
begin
    _classid = 'pg_catalog.pg_class'::pg_catalog.regclass::pg_catalog.oid;
    _objid = relation::pg_catalog.oid;
    _objsubid = 0;

    select k.relkind into strict _relkind
    from pg_catalog.pg_class k
    where k.oid operator(pg_catalog.=) _objid
    ;
    if _relkind not in ('r', 'f', 'p', 'v', 'm') then
        raise exception 'relkind % not supported', _relkind;
    end if;

    perform ai._set_description(_classid, _objid, _objsubid, description);
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- generate_description
create or replace function ai.generate_description
( relation pg_catalog.regclass
, catalog_name text default 'default'
, config jsonb default null
, save boolean default false
, overwrite boolean default false
) returns table
( name text
, description text
, sql text
)
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.semantic_catalog
    return ai.semantic_catalog.generate_description(plpy, relation, catalog_name, config, save, overwrite)
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- delete_description
create or replace function ai.delete_description(relation pg_catalog.regclass) returns void
as $func$
    delete from ai.semantic_catalog_obj d
    where d.classid = 'pg_catalog.pg_class'::pg_catalog.regclass::pg_catalog.oid
    and d.objid = relation::pg_catalog.oid
    and objsubid = 0
    ;
$func$ language sql volatile security invoker
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
    and not a.attisdropped
    ;
    if not found then
        raise exception '% column not found', column_name;
    end if;

    perform ai._set_description(_classid, _objid, _objsubid, description);
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- generate_column_descriptions
create or replace function ai.generate_column_descriptions
( relation pg_catalog.regclass
, catalog_name text default 'default'
, config jsonb default null
, save boolean default false
, overwrite boolean default false
) returns table
( column_name text
, description text
, sql text
)
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.semantic_catalog
    yield from ai.semantic_catalog.generate_column_descriptions(plpy, relation, catalog_name, config, save, overwrite)
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- delete_column_description
create or replace function ai.delete_column_description
( relation pg_catalog.regclass
, column_name pg_catalog.name
) returns void
as $func$
    with x as
    (
        select a.attnum
        from pg_catalog.pg_class k
        inner join pg_catalog.pg_attribute a on (k.oid operator(pg_catalog.=) a.attrelid)
        where k.oid operator(pg_catalog.=) 'pg_catalog.pg_class'::pg_catalog.regclass::pg_catalog.oid
        and k.relkind in ('r', 'f', 'p', 'v', 'm')
        and a.attnum operator(pg_catalog.>) 0
        and a.attname operator(pg_catalog.=) column_name
        and not a.attisdropped
    )
    delete from ai.semantic_catalog_obj d
    using x
    where d.classid = 'pg_catalog.pg_class'::pg_catalog.regclass::pg_catalog.oid
    and d.objid = relation::pg_catalog.oid
    and objsubid = x.attnum
    ;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- delete_column_descriptions
create or replace function ai.delete_column_descriptions
( relation pg_catalog.regclass
) returns void
as $func$
    delete from ai.semantic_catalog_obj d
    where d.classid = 'pg_catalog.pg_class'::pg_catalog.regclass::pg_catalog.oid
    and d.objid = relation::pg_catalog.oid
    and objsubid operator(pg_catalog.>) 0
    ;
$func$ language sql volatile security invoker
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
-- generate_function_description
create or replace function ai.generate_function_description
( fn regprocedure
, catalog_name text default 'default'
, config jsonb default null
, save boolean default false
, overwrite boolean default false
) returns table
( column_name text
, description text
, sql text
)
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.semantic_catalog
    yield from ai.semantic_catalog.generate_function_description(plpy, fn, catalog_name, config, save, overwrite)
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- delete_function_description
create or replace function ai.delete_function_description
( fn regprocedure
) returns void
as $func$
    delete from ai.semantic_catalog_obj d
    where d.classid = 'pg_catalog.pg_proc'::pg_catalog.regclass::pg_catalog.oid
    and d.objid = fn::pg_catalog.oid
    and objsubid operator(pg_catalog.>) 0
    ;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp;
