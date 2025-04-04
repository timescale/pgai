
-------------------------------------------------------------------------------
-- embedding_sentence_transformers
create or replace function ai.embedding_sentence_transformers
( model text default 'nomic-ai/nomic-embed-text-v1.5'
, dimensions int4 default 768
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'sentence_transformers'
    , 'config_type': 'embedding'
    , 'model': model
    , 'dimensions': dimensions
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _semantic_catalog_make_trigger
create or replace function ai._semantic_catalog_make_triggers(semantic_catalog_id int4) returns void
as $func$
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
-- semantic_catalog_add_embedding_config
create or replace function ai.semantic_catalog_add_embedding_config
( embedding jsonb
, catalog_name text default 'default'
) returns void
as $func$
declare
    _cat ai.semantic_catalog;
    _dims int4;
    _col_id int4;
    _tbl text;
    _sql text;
begin
    _dims = (embedding->'dimensions')::int4;
    assert _dims is not null, 'embedding config is missing dimensions';
    
    -- grab the catalog row
    select * into strict _cat
    from ai.semantic_catalog
    where name = catalog_name
    ;
    
    -- find the next available emb column id
    select coalesce(max(((regexp_match(x.key, '[0-9]+$'))[1])::int4) + 1, 1)
    into strict _col_id
    from jsonb_each(_cat.config->'embeddings') x
    ;
    raise debug '%', _col_id;
    
    -- add the embedding config
    update ai.semantic_catalog
    set config = jsonb_set
    ( config
    , array['embeddings', 'emb'||_col_id]
    , embedding
    , true
    )
    where id = _cat.id
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
        , _cat.id
        , 'emb' || _col_id
        , _dims
        );
        raise debug '%', _sql;
        execute _sql;
    end loop;
    
    perform ai._semantic_catalog_make_triggers(_cat.id);
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- semantic_catalog_drop_embedding_config
create or replace function ai.semantic_catalog_drop_embedding_config
( column_name name
, catalog_name text default 'default'
) returns void
as $func$
declare
    _id int4;
    _exists boolean;
    _tbl text;
    _sql text;
begin
    -- find the catalog id and ensure the embedding config exists
    select 
      x.id
    , x.config->'embeddings' ? column_name
    into strict
      _id
    , _exists
    from ai.semantic_catalog x
    where x.name = catalog_name
    ;
    if not _exists then
        raise exception 'column not found';
    end if;

    -- delete the embedding config
    update ai.semantic_catalog
    set config = jsonb_set
    ( config
    , array['embeddings']
    , (config->'embeddings') - column_name
    , true
    )
    where name = catalog_name
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
        , _id
        , column_name
        );
        raise debug '%', _sql;
        execute _sql;
    end loop;
    
    perform ai._semantic_catalog_make_triggers(_id);
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- create_semantic_catalog
create or replace function ai.create_semantic_catalog
( catalog_name text default 'default'
, embedding jsonb default ai.embedding_sentence_transformers()
) returns int4
as $func$
declare
    _id int4;
    _sql text;
begin
    insert into ai.semantic_catalog
    ( name
    , config
    )
    values 
    ( catalog_name
    , jsonb_build_object('embeddings', jsonb_build_object())
    )
    returning id into strict _id;
    
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
        , unique (classid, objid, objsubid)
        , unique (objtype, objnames, objargs)
        )
      $sql$
    , _id
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
        )
      $sql$
    , _id
    );
    raise debug '%', _sql;
    execute _sql;
    
    -- create the table for facts
    _sql = format
    ( $sql$
        create table ai.semantic_catalog_fact_%s
        ( id int8 not null primary key generated by default as identity
        , description text not null
        )
      $sql$
    , _id
    );
    raise debug '%', _sql;
    execute _sql;
    
    perform ai.semantic_catalog_add_embedding_config(embedding, catalog_name);
    
    return _id;
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- drop_semantic_catalog
create or replace function ai.drop_semantic_catalog(catalog_name text) returns int4
as $func$
declare
    _name text = drop_semantic_catalog.catalog_name;
    _id int4;
    _sql text;
    _tbl text;
begin
    delete from ai.semantic_catalog 
    where name = _name
    returning id into strict _id
    ;

    -- drop the table for database objects
    _sql = format
    ( $sql$
        drop table if exists ai.semantic_catalog_obj_%s
      $sql$
    , _id
    );
    raise debug '%', _sql;
    execute _sql;
    
    -- drop the table for example sql
    _sql = format
    ( $sql$
        drop table if exists ai.semantic_catalog_sql_%s
      $sql$
    , _id
    );
    raise debug '%', _sql;
    execute _sql;
    
    -- drop the table for facts
    _sql = format
    ( $sql$
        drop table if exists ai.semantic_catalog_fact_%s
      $sql$
    , _id
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
        , _id
        );
        raise debug '%', _sql;
        execute _sql;
    end loop;
    
    return _id;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

