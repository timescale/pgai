
-------------------------------------------------------------------------------
-- embedding_sentence_transformers
create or replace function ai.embedding_sentence_transformers
( model text default 'nomic-ai/nomic-embed-text-v1.5'
, dimensions int4 default 768
) returns jsonb
as $func$
    select json_build_object
    ( 'implementation', 'sentence_transformers'
    , 'config_type', 'embedding'
    , 'model', model
    , 'dimensions', dimensions
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-- TODO: function to validate embedding_sentence_transformers config

-------------------------------------------------------------------------------
-- _semantic_catalog_make_trigger
create or replace function ai._semantic_catalog_make_triggers(semantic_catalog_id int4) returns void
as $func$
/*
this function dynamically creates triggers on the obj, sql, and fact tables associated with a
semantic catalog. if any non-vector columns are updated, the vector columns are nulled out by
these triggers. this serves as the signal that the row should be reembedded
*/
declare
    _tbl text;
    _sql text;
    _vec_type oid;
    _vec_nulls text;
    _col_diffs text;
begin
    -- find the oid of the vector data type
    select y.oid into strict _vec_type
    from pg_type y
    inner join pg_depend d on (y.oid = d.objid)
    inner join pg_extension x on (x.oid = d.refobjid)
    where d.classid = 'pg_catalog.pg_type'::regclass::oid
    and d.refclassid = 'pg_catalog.pg_extension'::regclass::oid
    and d.deptype = 'e'
    and x.extname = 'vector'
    and y.typname = 'vector'
    ;

    foreach _tbl in array array['obj', 'sql', 'fact']
    loop
        select string_agg
        (
          format
          ( $sql$new.%s = null;$sql$
          , a.attname
          )
        , E'\n        '
        order by a.attnum
        ) filter (where a.atttypid = _vec_type)
        , string_agg
        (
          format
          ( $sql$(old.%s != new.%s)$sql$
          , a.attname
          , a.attname
          )
        , E'\n    or '
        order by a.attnum
        ) filter (where a.atttypid != _vec_type)
        into strict 
          _vec_nulls
        , _col_diffs
        from pg_class k
        inner join pg_namespace n on (k.relnamespace = n.oid)
        inner join pg_attribute a on (k.oid = a.attrelid)
        where n.nspname = 'ai'
        and k.relname = format('semantic_catalog_%s_%s', _tbl, semantic_catalog_id)
        and a.attnum > 0
        and not a.attisdropped
        ;
        
        _sql = format(regexp_replace(
        $sql$
        create or replace function ai.semantic_catalog_%s_%s_trig() returns trigger
        as $trigger$
        declare
        begin
            if tg_op = 'UPDATE' and
            (  %s
            )
            then
                %s
            end if;
            return new;
        end
        $trigger$ language plpgsql volatile security invoker
        set search_path to pg_catalog, pg_temp
        $sql$, '^ {8}', '', 'gm') -- dedent 8 spaces
        , _tbl
        , semantic_catalog_id
        , _col_diffs
        , _vec_nulls
        );
        raise debug '%', _sql;
        execute _sql;
        
        perform
        from pg_class k
        inner join pg_namespace n on (k.relnamespace = n.oid)
        inner join pg_trigger g on (g.tgrelid = k.oid)
        where n.nspname = 'ai'
        and k.relname = format('semantic_catalog_%s_%s', _tbl, semantic_catalog_id)
        and g.tgname = format('semantic_catalog_%s_%s_trig', _tbl, semantic_catalog_id)
        ;
        if not found then
            _sql = format(regexp_replace(
            $sql$
            create trigger semantic_catalog_%s_%s_trig 
            before update on ai.semantic_catalog_%s_%s
            for each row
            execute function ai.semantic_catalog_%s_%s_trig()
            $sql$, '^ {12}', '', 'gm') -- dedent 12 spaces
            , _tbl
            , semantic_catalog_id
            , _tbl
            , semantic_catalog_id
            , _tbl
            , semantic_catalog_id
            );
            raise debug '%', _sql;
            execute _sql;
        end if;
    end loop;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_add_embedding
create or replace function ai.sc_add_embedding
( config jsonb
, embedding_name name default null
, catalog_name name default 'default'
) returns ai.semantic_catalog_embedding
as $func$
declare
    _config jsonb = sc_add_embedding.config;
    _embedding_name name = sc_add_embedding.embedding_name;
    _catalog_name name = sc_add_embedding.catalog_name;
    _catalog_id int4;
    _dims int4;
    _tbl text;
    _sql text;
    _embedding ai.semantic_catalog_embedding;
begin
    -- TODO: validate embedding config

    _dims = (_config->'dimensions')::int4;
    assert _dims is not null, 'embedding config is missing dimensions';
    
    -- grab the catalog id
    select c.id into strict _catalog_id
    from ai.semantic_catalog c
    where c.catalog_name = _catalog_name
    ;
    
    if _embedding_name is null then
        select 'emb' ||
        greatest
        ( count(*)::int4
        , max((regexp_match(e.embedding_name, '[0-9]+$'))[1]::int4)
        ) + 1
        into strict _embedding_name
        from ai.semantic_catalog_embedding e
        where e.semantic_catalog_id = _catalog_id
        ;
    end if;
    
    insert into ai.semantic_catalog_embedding (semantic_catalog_id, embedding_name, config)
    values (_catalog_id, _embedding_name, _config)
    returning * into strict _embedding
    ;
    
    -- add the columns
    foreach _tbl in array array['obj', 'sql', 'fact']
    loop
        _sql = format
        (
        $sql$
            alter table ai.semantic_catalog_%s_%s add column %s @extschema:vector@.vector(%s)
        $sql$
        , _tbl
        , _catalog_id
        , _embedding_name
        , _dims
        );
        raise debug '%', _sql;
        execute _sql;
    end loop;
    
    perform ai._semantic_catalog_make_triggers(_catalog_id);
    
    return _embedding;
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_drop_embedding
create or replace function ai.sc_drop_embedding
( embedding_name name
, catalog_name name default 'default'
) returns void
as $func$
declare
    _embedding_name name = sc_drop_embedding.embedding_name;
    _catalog_name name = sc_drop_embedding.catalog_name;
    _embedding ai.semantic_catalog_embedding;
    _catalog_id int4;
    _tbl text;
    _sql text;
begin

    select c.id into strict _catalog_id
    from ai.semantic_catalog c
    where c.catalog_name = _catalog_name
    ;

    delete from ai.semantic_catalog_embedding e
    where e.semantic_catalog_id = _catalog_id
    and e.embedding_name = _embedding_name
    returning * into strict _embedding
    ;
    
    -- drop the columns
    foreach _tbl in array array['obj', 'sql', 'fact']
    loop
        _sql = format
        (
        $sql$
            alter table ai.semantic_catalog_%s_%s drop column %s
        $sql$
        , _tbl
        , _catalog_id
        , _embedding_name
        );
        raise debug '%', _sql;
        execute _sql;
    end loop;
    
    perform ai._semantic_catalog_make_triggers(_catalog_id);
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- create_semantic_catalog
create or replace function ai.create_semantic_catalog
( catalog_name name default 'default'
, embedding_name name default null
, embedding_config jsonb default ai.embedding_sentence_transformers()
) returns int4
as $func$
declare
    _catalog_name name = create_semantic_catalog.catalog_name;
    _embedding_name name = create_semantic_catalog.embedding_name;
    _embedding_config jsonb = create_semantic_catalog.embedding_config;
    _catalog_id int4;
    _sql text;
begin
    select nextval('ai.semantic_catalog_id_seq')
    into strict _catalog_id
    ;

    insert into ai.semantic_catalog
    ( id
    , catalog_name
    , obj_table
    , sql_table
    , fact_table
    )
    values 
    ( _catalog_id
    , catalog_name
    , array['ai', format('semantic_catalog_obj_%s', _catalog_id)]
    , array['ai', format('semantic_catalog_sql_%s', _catalog_id)]
    , array['ai', format('semantic_catalog_fact_%s', _catalog_id)]
    )
    ;
    
    -- create the table for database objects
    _sql = format
    ( $sql$
        create table ai.semantic_catalog_obj_%s
        ( id int8 not null primary key generated by default as identity
        , classid oid not null
        , objid oid not null
        , objsubid int4 not null
        , objtype text not null
        , objnames text[] not null
        , objargs text[] not null
        , description text
        , usage int8 not null default 0
        , unique (classid, objid, objsubid) deferrable initially immediate
        , unique (objtype, objnames, objargs) deferrable initially immediate
        )
      $sql$
    , _catalog_id
    );
    raise debug '%', _sql;
    execute _sql;
    
    -- create the table for example sql
    _sql = format
    ( $sql$
        create table ai.semantic_catalog_sql_%s
        ( id int8 not null primary key generated by default as identity
        , sql text not null
        , description text not null
        , usage int8 not null default 0
        )
      $sql$
    , _catalog_id
    );
    raise debug '%', _sql;
    execute _sql;
    
    -- create the table for facts
    _sql = format
    ( $sql$
        create table ai.semantic_catalog_fact_%s
        ( id int8 not null primary key generated by default as identity
        , description text not null
        , usage int8 not null default 0
        )
      $sql$
    , _catalog_id
    );
    raise debug '%', _sql;
    execute _sql;
    
    perform ai.sc_add_embedding
    ( embedding_name=>_embedding_name
    , config=>_embedding_config
    , catalog_name=>_catalog_name
    );
    
    return _catalog_id;
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- drop_semantic_catalog
create or replace function ai.drop_semantic_catalog(catalog_name name) returns int4
as $func$
declare
    _catalog_name name = drop_semantic_catalog.catalog_name;
    _catalog_id int4;
    _sql text;
    _tbl text;
begin
    delete from ai.semantic_catalog c
    where c.catalog_name = _catalog_name
    returning c.id into strict _catalog_id
    ;

    -- drop the table for database objects
    _sql = format
    ( $sql$
        drop table if exists ai.semantic_catalog_obj_%s
      $sql$
    , _catalog_id
    );
    raise debug '%', _sql;
    execute _sql;
    
    -- drop the table for example sql
    _sql = format
    ( $sql$
        drop table if exists ai.semantic_catalog_sql_%s
      $sql$
    , _catalog_id
    );
    raise debug '%', _sql;
    execute _sql;
    
    -- drop the table for facts
    _sql = format
    ( $sql$
        drop table if exists ai.semantic_catalog_fact_%s
      $sql$
    , _catalog_id
    );
    raise debug '%', _sql;
    execute _sql;
    
    -- drop trigger functions
    for _tbl in (values ('obj', 'sql', 'fact'))
    loop
        _sql = format
        ( $sql$
            drop function if exists ai.semantic_catalog_%s_%s_trig()
          $sql$
        , _tbl
        , _catalog_id
        );
        raise debug '%', _sql;
        execute _sql;
    end loop;
    
    return _catalog_id;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_grant_read
create or replace function ai.sc_grant_read(catalog_name name, role_name name) returns void
as $func$
declare
    _catalog_name name = sc_grant_read.catalog_name;
    _role_name name = sc_grant_read.role_name;
    _catalog_id int;
    _sql text;
begin
    select x.id into strict _catalog_id
    from ai.semantic_catalog x
    where x.catalog_name = _catalog_name
    ;

    _sql = format($sql$grant usage on schema ai to %I$sql$, _role_name);
    raise debug '%', _sql;
    execute _sql;

    for _sql in
    (
        select format(x, _role_name)
        from unnest(array[
            $sql$grant select on ai.semantic_catalog to %I$sql$,
            $sql$grant select on ai.semantic_catalog_embedding to %I$sql$
        ]) x
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;

    for _sql in
    (
        select format(y, x.id, _role_name)
        from ai.semantic_catalog x
        cross join unnest(array[
            $sql$grant select on ai.semantic_catalog_obj_%s to %I$sql$,
            $sql$grant select on ai.semantic_catalog_sql_%s to %I$sql$,
            $sql$grant select on ai.semantic_catalog_fact_%s to %I$sql$
        ]) y
        where x.catalog_name = _catalog_name
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_grant_write
create or replace function ai.sc_grant_write(catalog_name name, role_name name) returns void
as $func$
declare
    _catalog_name name = sc_grant_write.catalog_name;
    _role_name name = sc_grant_write.role_name;
    _catalog_id int;
    _sql text;
begin
    select x.id into strict _catalog_id
    from ai.semantic_catalog x
    where x.catalog_name = _catalog_name
    ;

    _sql = format($sql$grant usage on schema ai to %I$sql$, _role_name);
    raise debug '%', _sql;
    execute _sql;

    for _sql in
    (
        select format(x, _role_name)
        from unnest(array[
            $sql$grant select on ai.semantic_catalog to %I$sql$,
            $sql$grant select on ai.semantic_catalog_embedding to %I$sql$
        ]) x
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;

    for _sql in
    (
        select format(y, x.id, _role_name)
        from ai.semantic_catalog x
        cross join unnest(array[
            $sql$grant select, insert, update, delete on ai.semantic_catalog_obj_%s to %I$sql$,
            $sql$grant usage, select, update on sequence ai.semantic_catalog_obj_%s_id_seq to %I$sql$,
            $sql$grant select, insert, update, delete on ai.semantic_catalog_sql_%s to %I$sql$,
            $sql$grant usage, select, update on sequence ai.semantic_catalog_sql_%s_id_seq to %I$sql$,
            $sql$grant select, insert, update, delete on ai.semantic_catalog_fact_%s to %I$sql$,
            $sql$grant usage, select, update on sequence ai.semantic_catalog_fact_%s_id_seq to %I$sql$
        ]) y
        where x.catalog_name = _catalog_name
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_grant_admin
create or replace function ai.sc_grant_admin(role_name name) returns void
as $func$
declare
    _role_name name = sc_grant_admin.role_name;
    _sql text;
begin

    _sql = format($sql$grant usage on schema ai to %I$sql$, _role_name);
    raise debug '%', _sql;
    execute _sql;

    for _sql in
    (
        select format(x, _role_name)
        from unnest(array[
            $sql$grant select, insert, update, delete, truncate on ai.semantic_catalog to %I$sql$,
            $sql$grant usage, select, update on sequence ai.semantic_catalog_id_seq to %I$sql$,
            $sql$grant select, insert, update, delete, truncate on ai.semantic_catalog_embedding to %I$sql$,
            $sql$grant usage, select, update on sequence ai.semantic_catalog_embedding_id_seq to %I$sql$
        ]) x
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;

    for _sql in
    (
        select format(y, x.id, _role_name)
        from ai.semantic_catalog x
        cross join unnest(array[
            $sql$grant select, insert, update, delete on ai.semantic_catalog_obj_%s to %I$sql$,
            $sql$grant usage, select, update on sequence ai.semantic_catalog_obj_%s_id_seq to %I$sql$,
            $sql$grant select, insert, update, delete on ai.semantic_catalog_sql_%s to %I$sql$,
            $sql$grant usage, select, update on sequence ai.semantic_catalog_sql_%s_id_seq to %I$sql$,
            $sql$grant select, insert, update, delete on ai.semantic_catalog_fact_%s to %I$sql$,
            $sql$grant usage, select, update on sequence ai.semantic_catalog_fact_%s_id_seq to %I$sql$
        ]) y
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _sc_obj
create or replace function ai._sc_obj(catalog_id int)
returns table
( id int8
, classid oid
, objid oid
, objsubid int4
, objtype text
, objnames text[]
, objargs text[]
, description text
)
as $func$
declare
    _sql text;
begin
    _sql = format
    ( $sql$
        select
          id
        , classid
        , objid
        , objsubid
        , objtype
        , objnames
        , objargs
        , description
        from ai.semantic_catalog_obj_%s
      $sql$
    , catalog_id
    );
    return query execute _sql;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_grant_obj_read
create or replace function ai.sc_grant_obj_read(catalog_name name, role_name name) returns void
as $func$
/*
    grants select/execute on all database objects referenced in the specified catalog
    grants usage on the schemas to which those objects belong
*/
declare
    _catalog_name name = sc_grant_obj_read.catalog_name;
    _role_name name = sc_grant_obj_read.role_name;
    _catalog_id int;
    _sql text;
begin
    select x.id into strict _catalog_id
    from ai.semantic_catalog x
    where x.catalog_name = _catalog_name
    ;
    
    if not has_table_privilege
        ( _role_name
        , format('ai.semantic_catalog_obj_%s', _catalog_id)
        , 'select'
        ) then
        raise exception 'user must have access to the catalog first';
    end if;

    -- schemas
    for _sql in
    (
        select format
        ( $sql$grant usage on schema %I to %I$sql$
        , x.schema_name
        , _role_name
        )
        from
        (
            select distinct x.objnames[1] as schema_name
            from ai._sc_obj(_catalog_id) x
            where x.objsubid = 0
        ) x
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;

    -- objects
    for _sql in
    (
        select format
        ( $sql$grant %s on %s %I.%I%s to %I$sql$
        , case when x.objtype in ('aggregate', 'function', 'procedure')
            then 'execute'
            else 'select'
          end
        , case
            when x.objtype in ('function', 'aggregate') then 'function'
            else x.objtype
          end
        , x.objnames[1]
        , x.objnames[2]
        , case when x.objtype in ('aggregate', 'function', 'procedure')
            then format('(%s)', array_to_string(x.objargs, ', '))
            else ''
          end
        , _role_name
        )
        from ai._sc_obj(_catalog_id) x
        where x.objsubid = 0
        order by x.objnames
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_obj_desc
create or replace function ai.sc_set_obj_desc
( classid oid
, objid oid
, objsubid integer
, objtype text
, objnames text[]
, objargs text[]
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
declare
    _catalog_name name = sc_set_obj_desc.catalog_name;
    _sql text;
    _id int8;
begin
    select format
    ( $sql$
        merge into ai.semantic_catalog_obj_%s tgt
        using
        (
            select
              $1 as classid
            , $2 as objid
            , $3 as objsubid
            , $4 as objtype
            , $5 as objnames
            , $6 as objargs
            , $7 as description
        ) src
        on (tgt.classid = src.classid and tgt.objid = src.objid and tgt.objsubid = src.objsubid)
        when matched then update set description = src.description
        when not matched by target then
        insert
        ( classid
        , objid
        , objsubid
        , objtype
        , objnames
        , objargs
        , description
        )
        values
        ( src.classid
        , src.objid
        , src.objsubid
        , src.objtype
        , src.objnames
        , src.objargs
        , src.description
        )
        returning id
      $sql$
    , x.id
    ) into strict _sql
    from ai.semantic_catalog x
    where x.catalog_name = _catalog_name
    ;
    execute _sql using
      classid
    , objid
    , objsubid
    , objtype
    , objnames
    , objargs
    , description
    into strict _id;
    return _id;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_table_desc
create or replace function ai.sc_set_table_desc
( classid oid
, objid oid
, schema_name name
, table_name name
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
    select *
    from ai.sc_set_obj_desc
    ( classid
    , objid
    , 0
    , 'table'
    , array[schema_name, table_name]
    , array[]::text[]
    , description
    , catalog_name
    );
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_table_col_desc
create or replace function ai.sc_set_table_col_desc
( classid oid
, objid oid
, objsubid int4
, schema_name name
, table_name name
, column_name name
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
    select *
    from ai.sc_set_obj_desc
    ( classid
    , objid
    , objsubid
    , 'table column'
    , array[schema_name, table_name, column_name]
    , array[]::text[]
    , description
    , catalog_name
    );
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_view_desc
create or replace function ai.sc_set_view_desc
( classid oid
, objid oid
, schema_name name
, view_name name
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
    select *
    from ai.sc_set_obj_desc
    ( classid
    , objid
    , 0
    , 'view'
    , array[schema_name, view_name]
    , array[]::text[]
    , description
    , catalog_name
    );
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_view_col_desc
create or replace function ai.sc_set_view_col_desc
( classid oid
, objid oid
, objsubid int4
, schema_name name
, view_name name
, column_name name
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
    select *
    from ai.sc_set_obj_desc
    ( classid
    , objid
    , objsubid
    , 'view column'
    , array[schema_name, view_name, column_name]
    , array[]::text[]
    , description
    , catalog_name
    );
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_proc_desc
create or replace function ai.sc_set_proc_desc
( classid oid
, objid oid
, schema_name name
, proc_name name
, objargs text[]
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
    select *
    from ai.sc_set_obj_desc
    ( classid
    , objid
    , 0
    , 'procedure'
    , array[schema_name, proc_name]
    , coalesce(objargs, array[]::text[])
    , description
    , catalog_name
    );
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_func_desc
create or replace function ai.sc_set_func_desc
( classid oid
, objid oid
, schema_name name
, func_name name
, objargs text[]
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
    select *
    from ai.sc_set_obj_desc
    ( classid
    , objid
    , 0
    , 'function'
    , array[schema_name, func_name]
    , coalesce(objargs, array[]::text[])
    , description
    , catalog_name
    );
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_agg_desc
create or replace function ai.sc_set_agg_desc
( classid oid
, objid oid
, schema_name name
, agg_name name
, objargs text[]
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
    select *
    from ai.sc_set_obj_desc
    ( classid
    , objid
    , 0
    , 'aggregate'
    , array[schema_name, agg_name]
    , coalesce(objargs, array[]::text[])
    , description
    , catalog_name
    );
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_obj_desc
create or replace function ai.sc_set_obj_desc
( objtype text
, objnames text[]
, objargs text[]
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
declare
    _classid oid;
    _objid oid;
    _objsubid integer;
begin
    select
      x.classid
    , x.objid
    , x.subobjid
    into strict
      _classid
    , _objid
    , _objsubid
    from pg_get_object_address(objtype, objnames, objargs) x
    ;
    return ai.sc_set_obj_desc
    ( _classid
    , _objid
    , _objsubid
    , objtype
    , objnames
    , objargs
    , description
    , catalog_name
    );
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_table_desc
create or replace function ai.sc_set_table_desc
( t regclass
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
    select ai.sc_set_obj_desc
    ( 'pg_catalog.pg_class'::regclass::oid
    , t
    , 0
    , x.type
    , x.object_names
    , x.object_args
    , description
    , catalog_name
    )
    from pg_class k
    cross join pg_identify_object_as_address
    ( 'pg_catalog.pg_class'::regclass::oid
    , t
    , 0
    ) x
    where k.oid = t
    and k.relkind in ('r', 'p', 'f')
    ;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_table_col_desc
create or replace function ai.sc_set_table_col_desc
( t regclass
, column_name name
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
    select ai.sc_set_obj_desc
    ( 'pg_catalog.pg_class'::regclass::oid
    , t
    , a.attnum
    , x.type
    , x.object_names
    , x.object_args
    , description
    , catalog_name
    )
    from pg_class k
    inner join pg_attribute a on (k.oid = a.attrelid)
    cross join lateral pg_identify_object_as_address
    ( 'pg_catalog.pg_class'::regclass::oid
    , t
    , a.attnum
    ) x
    where k.oid = t
    and k.relkind in ('r', 'p', 'f')
    and a.attname = column_name
    ;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_view_desc
create or replace function ai.sc_set_view_desc
( v regclass
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
    select ai.sc_set_obj_desc
    ( 'pg_catalog.pg_class'::regclass::oid
    , v
    , 0
    , x.type
    , x.object_names
    , x.object_args
    , description
    , catalog_name
    )
    from pg_class k
    cross join pg_identify_object_as_address
    ( 'pg_catalog.pg_class'::regclass::oid
    , v
    , 0
    ) x
    where k.oid = v
    and k.relkind in ('v', 'm')
    ;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_view_col_desc
create or replace function ai.sc_set_view_col_desc
( v regclass
, column_name name
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
    select ai.sc_set_obj_desc
    ( 'pg_catalog.pg_class'::regclass::oid
    , v
    , a.attnum
    , x.type
    , x.object_names
    , x.object_args
    , description
    , catalog_name
    )
    from pg_class k
    inner join pg_attribute a on (k.oid = a.attrelid)
    cross join lateral pg_identify_object_as_address
    ( 'pg_catalog.pg_class'::regclass::oid
    , v
    , a.attnum
    ) x
    where k.oid = v
    and k.relkind in ('v', 'm')
    and a.attname = column_name
    ;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_proc_desc
create or replace function ai.sc_set_proc_desc
( p regprocedure
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
    select ai.sc_set_obj_desc
    ( 'pg_catalog.pg_proc'::regclass::oid
    , p
    , 0
    , x.type
    , x.object_names
    , x.object_args
    , description
    , catalog_name
    )
    from pg_proc o
    cross join pg_identify_object_as_address
    ( 'pg_catalog.pg_proc'::regclass::oid
    , p
    , 0
    ) x
    where o.oid = p
    and o.prokind = 'p'
    ;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_func_desc
create or replace function ai.sc_set_func_desc
( f regprocedure
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
    select ai.sc_set_obj_desc
    ( 'pg_catalog.pg_proc'::regclass::oid
    , f
    , 0
    , x.type
    , x.object_names
    , x.object_args
    , description
    , catalog_name
    )
    from pg_proc o
    cross join pg_identify_object_as_address
    ( 'pg_catalog.pg_proc'::regclass::oid
    , f
    , 0
    ) x
    where o.oid = f
    and o.prokind in ('f', 'w')
    ;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_set_agg_desc
create or replace function ai.sc_set_agg_desc
( a regprocedure
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
    select ai.sc_set_obj_desc
    ( 'pg_catalog.pg_proc'::regclass::oid
    , a
    , 0
    , x.type
    , x.object_names
    , x.object_args
    , description
    , catalog_name
    )
    from pg_proc o
    cross join pg_identify_object_as_address
    ( 'pg_catalog.pg_proc'::regclass::oid
    , a
    , 0
    ) x
    where o.oid = a
    and o.prokind = 'a'
    ;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_add_sql_desc
create or replace function ai.sc_add_sql_desc
( sql text
, description text
, catalog_name name default 'default'
)
returns int8
as $func$
declare
    _catalog_name name = sc_add_sql_desc.catalog_name;
    _sql text;
    _id int8;
begin
    select format
    ( $sql$
        insert into ai.semantic_catalog_sql_%s
        ( sql
        , description
        )
        values
        ( $1
        , $2
        )
        returning id
      $sql$
    , x.id
    ) into strict _sql
    from ai.semantic_catalog x
    where x.catalog_name = _catalog_name
    ;
    execute _sql using
      sql
    , description
    into strict _id;
    return _id;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_update_sql_desc
create or replace function ai.sc_update_sql_desc
( id int8
, sql text
, description text
, catalog_name name default 'default'
)
returns void
as $func$
declare
    _catalog_name name = sc_update_sql_desc.catalog_name;
    _sql text;
begin
    select format
    ( $sql$
        update ai.semantic_catalog_sql_%s set
          sql = $1
        , description = $2
        where id = $3
      $sql$
    , x.id
    ) into strict _sql
    from ai.semantic_catalog x
    where x.catalog_name = _catalog_name
    ;
    execute _sql using
      sql
    , description
    , id
    ;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_add_fact
create or replace function ai.sc_add_fact
( description text
, catalog_name name default 'default'
)
returns int8
as $func$
declare
    _catalog_name name = sc_add_fact.catalog_name;
    _sql text;
    _id int8;
begin
    select format
    ( $sql$
        insert into ai.semantic_catalog_fact_%s
        ( description
        )
        values
        ( $1
        )
        returning id
      $sql$
    , x.id
    ) into strict _sql
    from ai.semantic_catalog x
    where x.catalog_name = _catalog_name
    ;
    execute _sql using description
    into strict _id;
    return _id;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- sc_update_fact
create or replace function ai.sc_update_fact
( id int8
, description text
, catalog_name name default 'default'
)
returns void
as $func$
declare
    _catalog_name name = sc_update_fact.catalog_name;
    _sql text;
begin
    select format
    ( $sql$
        update ai.semantic_catalog_fact_%s set description = $1
        where id = $2
      $sql$
    , x.id
    ) into strict _sql
    from ai.semantic_catalog x
    where x.catalog_name = _catalog_name
    ;
    execute _sql using description, id;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

