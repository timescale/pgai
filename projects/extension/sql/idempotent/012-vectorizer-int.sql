
-------------------------------------------------------------------------------
-- _vectorizer_source_pk
create or replace function ai._vectorizer_source_pk(source_table pg_catalog.regclass) returns pg_catalog.jsonb as
$func$
    select pg_catalog.jsonb_agg(x)
    from
    (
        select e.attnum, e.pknum, a.attname, y.typname
        from pg_catalog.pg_constraint k
        cross join lateral pg_catalog.unnest(k.conkey) with ordinality e(attnum, pknum)
        inner join pg_catalog.pg_attribute a
            on (k.conrelid operator(pg_catalog.=) a.attrelid
                and e.attnum operator(pg_catalog.=) a.attnum)
        inner join pg_catalog.pg_type y on (a.atttypid operator(pg_catalog.=) y.oid)
        where k.conrelid operator(pg_catalog.=) source_table
        and k.contype operator(pg_catalog.=) 'p'
    ) x
$func$
language sql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_grant_to_source
create or replace function ai._vectorizer_grant_to_source
( source_schema pg_catalog.name
, source_table pg_catalog.name
, grant_to pg_catalog.name[]
) returns void as
$func$
declare
    _sql pg_catalog.text;
begin
    if grant_to is not null then
        -- grant usage on source schema to grant_to roles
        select pg_catalog.format
        ( $sql$grant usage on schema %I to %s$sql$
        , source_schema
        , (
            select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
            from pg_catalog.unnest(grant_to) x
          )
        ) into strict _sql;
        execute _sql;

        -- grant select on source table to grant_to roles
        select pg_catalog.format
        ( $sql$grant select on %I.%I to %s$sql$
        , source_schema
        , source_table
        , (
            select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
            from pg_catalog.unnest(grant_to) x
          )
        ) into strict _sql;
        execute _sql;
    end if;
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_grant_to_vectorizer
create or replace function ai._vectorizer_grant_to_vectorizer(grant_to pg_catalog.name[]) returns void as
$func$
declare
    _sql pg_catalog.text;
begin
    if grant_to is not null then
        -- grant usage on schema ai to grant_to roles
        select pg_catalog.format
        ( $sql$grant usage on schema ai to %s$sql$
        , (
            select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
            from pg_catalog.unnest(grant_to) x
          )
        ) into strict _sql;
        execute _sql;

        -- grant select on vectorizer table to grant_to roles
        select pg_catalog.format
        ( $sql$grant select on ai.vectorizer to %s$sql$
        , (
            select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
            from pg_catalog.unnest(grant_to) x
          )
        ) into strict _sql;
        execute _sql;
    end if;
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_create_target_table
create or replace function ai._vectorizer_create_target_table
( source_schema pg_catalog.name
, source_table pg_catalog.name
, source_pk pg_catalog.jsonb
, target_schema pg_catalog.name
, target_table pg_catalog.name
, dimensions pg_catalog.int4
, grant_to pg_catalog.name[]
) returns void as
$func$
declare
    _pk_cols pg_catalog.text;
    _sql pg_catalog.text;
begin
    select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.pknum)
    into strict _pk_cols
    from pg_catalog.jsonb_to_recordset(source_pk) x(pknum int, attname name)
    ;

    select pg_catalog.format
    ( $sql$
    create table %I.%I
    ( embedding_uuid uuid not null primary key default pg_catalog.gen_random_uuid()
    , %s
    , chunk_seq int not null
    , chunk text not null
    , embedding @extschema:vector@.vector(%L) storage main not null
    , unique (%s, chunk_seq)
    , foreign key (%s) references %I.%I (%s) on delete cascade
    )
    $sql$
    , target_schema, target_table
    , (
        select pg_catalog.string_agg
        (
            pg_catalog.format
            ( '%I %s not null'
            , x.attname
            , x.typname
            )
            , E'\n, '
            order by x.attnum
        )
        from pg_catalog.jsonb_to_recordset(source_pk)
            x(attnum int, attname name, typname name)
      )
    , dimensions
    , _pk_cols
    , _pk_cols
    , source_schema, source_table
    , _pk_cols
    ) into strict _sql
    ;
    execute _sql;

    if grant_to is not null then
        -- grant usage on target schema to grant_to roles
        select pg_catalog.format
        ( $sql$grant usage on schema %I to %s$sql$
        , target_schema
        , (
            select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
            from pg_catalog.unnest(grant_to) x
          )
        ) into strict _sql;
        execute _sql;

        -- grant select, insert, update on target table to grant_to roles
        select pg_catalog.format
        ( $sql$grant select, insert, update on %I.%I to %s$sql$
        , target_schema
        , target_table
        , (
            select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
            from pg_catalog.unnest(grant_to) x
          )
        ) into strict _sql;
        execute _sql;
    end if;
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_create_view
create or replace function ai._vectorizer_create_view
( view_schema pg_catalog.name
, view_name pg_catalog.name
, source_schema pg_catalog.name
, source_table pg_catalog.name
, source_pk pg_catalog.jsonb
, target_schema pg_catalog.name
, target_table pg_catalog.name
, grant_to pg_catalog.name[]
) returns void as
$func$
declare
    _sql pg_catalog.text;
begin
    select pg_catalog.format
    ( $sql$
    create view %I.%I as
    select
      t.embedding_uuid
    , t.chunk_seq
    , t.chunk
    , t.embedding
    , %s
    from %I.%I t
    left outer join %I.%I s
    on (%s)
    $sql$
    , view_schema, view_name
    , (
        -- take primary keys from the target table and other columns from source
        -- this allows for join removal optimization
        select pg_catalog.string_agg
        (
            pg_catalog.format
            ( '%s.%I'
            , case when x.attnum is not null then 't' else 's' end
            , a.attname
            )
            , E'\n    , '
            order by a.attnum
        )
        from pg_catalog.pg_attribute a
        left outer join pg_catalog.jsonb_to_recordset(source_pk) x(attnum int) on (a.attnum operator(pg_catalog.=) x.attnum)
        where a.attrelid operator(pg_catalog.=) pg_catalog.format('%I.%I', source_schema, source_table)::pg_catalog.regclass::pg_catalog.oid
        and a.attnum operator(pg_catalog.>) 0
        and not a.attisdropped
      )
    , target_schema, target_table
    , source_schema, source_table
    , (
        select pg_catalog.string_agg
        (
            pg_catalog.format
            ( 't.%s = s.%s'
            , x.attname
            , x.attname
            )
            , ' and '
            order by x.pknum
        )
        from pg_catalog.jsonb_to_recordset(source_pk)
            x(pknum int, attname name)
      )
    ) into strict _sql;
    execute _sql;

    if grant_to is not null then
        -- grant usage on view schema to grant_to roles
        select pg_catalog.format
        ( $sql$grant usage on schema %I to %s$sql$
        , view_schema
        , (
            select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
            from pg_catalog.unnest(grant_to) x
          )
        ) into strict _sql;
        execute _sql;

        -- grant select on view to grant_to roles
        select pg_catalog.format
        ( $sql$grant select on %I.%I to %s$sql$
        , view_schema
        , view_name
        , (
            select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
            from pg_catalog.unnest(grant_to) x
          )
        ) into strict _sql;
        execute _sql;
    end if;
end
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_create_dependencies
create or replace function ai._vectorizer_create_dependencies(vectorizer_id pg_catalog.int4)
returns void as
$func$
declare
    _vec ai.vectorizer%rowtype;
    _is_owner pg_catalog.bool;
begin
    -- this function is security definer since we need to insert into a catalog table
    -- fully-qualify everything and be careful of security holes

    -- we don't want to run this function on arbitrary tables, so we don't take
    -- schema/table names as parameters. we take a vectorizer id and look it up
    -- preventing this function from being abused
    select v.* into strict _vec
    from ai.vectorizer v
    where v.id operator(pg_catalog.=) vectorizer_id
    ;

    -- don't let anyone but a superuser or the owner (or members of the owner's role) of the source table call this
    select pg_catalog.pg_has_role(pg_catalog.session_user(), k.relowner, 'MEMBER')
    into strict _is_owner
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
    where k.oid operator(pg_catalog.=) pg_catalog.format('%I.%I', _vec.source_schema, _vec.source_table)::pg_catalog.regclass::pg_catalog.oid
    ;
    -- not an owner of the table, but superuser?
    if not _is_owner then
        select r.rolsuper into strict _is_owner
        from pg_catalog.pg_roles r
        where r.rolname operator(pg_catalog.=) pg_catalog.current_user()
        ;
    end if;
    if not _is_owner then
        raise exception 'only a superuser or the owner of the source table may call ai._vectorizer_create_dependencies';
    end if;

    -- if we drop the source or the target with `cascade` it should drop the queue
    -- if we drop the source with `cascade` it should drop the target
    -- there's no unique constraint on pg_depend so we manually prevent duplicate entries
    with x as
    (
        -- the queue table depends on the source table
        select
         (select oid from pg_catalog.pg_class where relname operator(pg_catalog.=) 'pg_class') as classid
        , pg_catalog.format('%I.%I', _vec.queue_schema, _vec.queue_table)::pg_catalog.regclass::pg_catalog.oid as objid
        , 0 as objsubid
        , (select oid from pg_catalog.pg_class where relname operator(pg_catalog.=) 'pg_class') as refclassid
        , pg_catalog.format('%I.%I', _vec.source_schema, _vec.source_table)::pg_catalog.regclass::pg_catalog.oid as refobjid
        , 0 as refobjsubid
        , 'n' as deptype
        union all
        -- the queue table depends on the target table
        select
         (select oid from pg_catalog.pg_class where relname operator(pg_catalog.=) 'pg_class') as classid
        , pg_catalog.format('%I.%I', _vec.queue_schema, _vec.queue_table)::pg_catalog.regclass::pg_catalog.oid as objid
        , 0 as objsubid
        , (select oid from pg_catalog.pg_class where relname operator(pg_catalog.=) 'pg_class') as refclassid
        , pg_catalog.format('%I.%I', _vec.target_schema, _vec.target_table)::pg_catalog.regclass::pg_catalog.oid as refobjid
        , 0 as refobjsubid
        , 'n' as deptype
        union all
        -- the target table depends on the source table
        select
         (select oid from pg_catalog.pg_class where relname operator(pg_catalog.=) 'pg_class') as classid
        , pg_catalog.format('%I.%I', _vec.target_schema, _vec.target_table)::pg_catalog.regclass::pg_catalog.oid as objid
        , 0 as objsubid
        , (select oid from pg_catalog.pg_class where relname operator(pg_catalog.=) 'pg_class') as refclassid
        , pg_catalog.format('%I.%I', _vec.source_schema, _vec.source_table)::pg_catalog.regclass::pg_catalog.oid as refobjid
        , 0 as refobjsubid
        , 'n' as deptype
    )
    insert into pg_catalog.pg_depend
    ( classid
    , objid
    , objsubid
    , refclassid
    , refobjid
    , refobjsubid
    , deptype
    )
    select
      x.classid
    , x.objid
    , x.objsubid
    , x.refclassid
    , x.refobjid
    , x.refobjsubid
    , x.deptype
    from x
    where not exists
    (
        select 1
        from pg_catalog.pg_depend d
        where d.classid operator(pg_catalog.=) x.classid
        and d.objid operator(pg_catalog.=) x.objid
        and d.objsubid operator(pg_catalog.=) x.objsubid
        and d.refclassid operator(pg_catalog.=) x.refclassid
        and d.refobjid operator(pg_catalog.=) x.refobjid
        and d.refobjsubid operator(pg_catalog.=) x.refobjsubid
        and d.deptype operator(pg_catalog.=) x.deptype
    )
    ;
end
$func$
language plpgsql volatile security definer -- definer on purpose
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_create_queue_table
create or replace function ai._vectorizer_create_queue_table
( queue_schema pg_catalog.name
, queue_table pg_catalog.name
, source_pk pg_catalog.jsonb
, grant_to pg_catalog.name[]
) returns void as
$func$
declare
    _sql pg_catalog.text;
begin
    -- create the table
    select pg_catalog.format
    ( $sql$create table %I.%I(%s, queued_at timestamptz not null default now())$sql$
    , queue_schema, queue_table
    , (
        select pg_catalog.string_agg
        (
          pg_catalog.format
          ( '%I %s not null'
          , x.attname
          , x.typname
          )
          , E'\n, '
          order by x.attnum
        )
        from pg_catalog.jsonb_to_recordset(source_pk) x(attnum int, attname name, typname name)
      )
    ) into strict _sql
    ;
    execute _sql;

    -- create the index
    select pg_catalog.format
    ( $sql$create index on %I.%I (%s)$sql$
    , queue_schema, queue_table
    , (
        select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.pknum)
        from pg_catalog.jsonb_to_recordset(source_pk) x(pknum int, attname name)
      )
    ) into strict _sql
    ;
    execute _sql;

    if grant_to is not null then
        -- grant usage on queue schema to grant_to roles
        select pg_catalog.format
        ( $sql$grant usage on schema %I to %s$sql$
        , queue_schema
        , (
            select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
            from pg_catalog.unnest(grant_to) x
          )
        ) into strict _sql;
        execute _sql;

        -- grant select, update, delete on queue table to grant_to roles
        select pg_catalog.format
        ( $sql$grant select, insert, update, delete on %I.%I to %s$sql$
        , queue_schema
        , queue_table
        , (
            select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
            from pg_catalog.unnest(grant_to) x
          )
        ) into strict _sql;
        execute _sql;
    end if;
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_create_source_trigger
create or replace function ai._vectorizer_create_source_trigger
( trigger_name pg_catalog.name
, queue_schema pg_catalog.name
, queue_table pg_catalog.name
, source_schema pg_catalog.name
, source_table pg_catalog.name
, source_pk pg_catalog.jsonb
) returns void as
$func$
declare
    _sql pg_catalog.text;
begin
    -- create the trigger function
    -- the trigger function is security definer
    -- the owner of the source table is creating the trigger function
    -- so the trigger function is run as the owner of the source table
    -- who also owns the queue table
    -- this means anyone with insert/update on the source is able
    -- to enqueue rows in the queue table automatically
    -- since the trigger function only does inserts, this should be safe
    select pg_catalog.format
    ( $sql$
    create function %I.%I() returns trigger
    as $plpgsql$
    begin
        insert into %I.%I (%s)
        values (%s);
        return null;
    end;
    $plpgsql$ language plpgsql volatile parallel safe security definer
    set search_path to pg_catalog, pg_temp
    $sql$
    , queue_schema, trigger_name
    , queue_schema, queue_table
    , (
        select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(source_pk) x(attnum int, attname name)
      )
    , (
        select pg_catalog.string_agg(pg_catalog.format('new.%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(source_pk) x(attnum int, attname name)
      )
    ) into strict _sql
    ;
    execute _sql;

    -- revoke all on trigger function from public
    select pg_catalog.format
    ( $sql$
    revoke all on function %I.%I() from public
    $sql$
    , queue_schema, trigger_name
    ) into strict _sql
    ;
    execute _sql;

    -- create the trigger on the source table
    select pg_catalog.format
    ( $sql$
    create trigger %I
    after insert or update
    on %I.%I
    for each row execute function %I.%I();
    $sql$
    , trigger_name
    , source_schema, source_table
    , queue_schema, trigger_name
    ) into strict _sql
    ;
    execute _sql;
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_vector_index_exists
create or replace function ai._vectorizer_vector_index_exists
( target_schema pg_catalog.name
, target_table pg_catalog.name
, indexing pg_catalog.jsonb
) returns pg_catalog.bool as
$func$
declare
    _implementation pg_catalog.text;
    _found pg_catalog.bool;
begin
    _implementation = pg_catalog.jsonb_extract_path_text(indexing, 'implementation');
    if _implementation not in ('diskann', 'hnsw') then
        raise exception 'unrecognized index implementation: %s', _implementation;
    end if;

    -- look for an index on the target table where the indexed column is the "embedding" column
    -- and the index is using the correct implementation
    select pg_catalog.count(*) filter
    ( where pg_catalog.pg_get_indexdef(i.indexrelid)
      ilike pg_catalog.concat('% using ', _implementation, ' %')
    ) > 0 into _found
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
    inner join pg_index i on (k.oid operator(pg_catalog.=) i.indrelid)
    inner join pg_catalog.pg_attribute a
        on (k.oid operator(pg_catalog.=) a.attrelid
        and a.attname operator(pg_catalog.=) 'embedding'
        and a.attnum operator(pg_catalog.=) i.indkey[0]
        )
    where n.nspname operator(pg_catalog.=) target_schema
    and k.relname operator(pg_catalog.=) target_table
    ;
    return coalesce(_found, false);
end
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_should_create_vector_index
create or replace function ai._vectorizer_should_create_vector_index(vectorizer ai.vectorizer) returns boolean
as $func$
declare
    _indexing pg_catalog.jsonb;
    _implementation pg_catalog.text;
    _create_when_queue_empty pg_catalog.bool;
    _sql pg_catalog.text;
    _count pg_catalog.int8;
    _min_rows pg_catalog.int8;
begin
    -- grab the indexing config
    _indexing = pg_catalog.jsonb_extract_path(vectorizer.config, 'indexing');
    if _indexing is null then
        return false;
    end if;

    -- grab the indexing config's implementation
    _implementation = pg_catalog.jsonb_extract_path_text(_indexing, 'implementation');
    -- if implementation is missing or none, exit
    if _implementation is null or _implementation = 'none' then
        return false;
    end if;

    -- see if the index already exists. if so, exit
    if ai._vectorizer_vector_index_exists(vectorizer.target_schema, vectorizer.target_table, _indexing) then
        return false;
    end if;

    -- if flag set, only attempt to create the vector index if the queue table is empty
    _create_when_queue_empty = coalesce(pg_catalog.jsonb_extract_path(_indexing, 'create_when_queue_empty')::pg_catalog.bool, true);
    if _create_when_queue_empty then
        -- count the rows in the queue table
        select pg_catalog.format
        ( $sql$select pg_catalog.count(1) from %I.%I limit 1$sql$
        , vectorizer.queue_schema
        , vectorizer.queue_table
        ) into strict _sql
        ;
        execute _sql into _count;
        if _count operator(pg_catalog.>) 0 then
            raise notice 'queue for %.% is not empty. skipping vector index creation', vectorizer.target_schema, vectorizer.target_table;
            return false;
        end if;
    end if;

    -- if min_rows has a value
    _min_rows = coalesce(pg_catalog.jsonb_extract_path_text(_indexing, 'min_rows')::pg_catalog.int8, 0);
    if _min_rows > 0 then
        -- count the rows in the target table
        select pg_catalog.format
        ( $sql$select pg_catalog.count(*) from (select 1 from %I.%I limit %L) x$sql$
        , vectorizer.target_schema
        , vectorizer.target_table
        , _min_rows
        ) into strict _sql
        ;
        execute _sql into _count;
    end if;

    -- if we have met or exceeded min_rows, create the index
    return coalesce(_count, 0) >= _min_rows;
end
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_create_vector_index
create or replace function ai._vectorizer_create_vector_index
( target_schema pg_catalog.name
, target_table pg_catalog.name
, indexing pg_catalog.jsonb
) returns void as
$func$
declare
    _key1 pg_catalog.int4 = 1982010642;
    _key2 pg_catalog.int4;
    _implementation pg_catalog.text;
    _with_count pg_catalog.int8;
    _with pg_catalog.text;
    _ext_schema pg_catalog.name;
    _sql pg_catalog.text;
begin

    -- use the target table's oid as the second key for the advisory lock
    select k.oid::pg_catalog.int4 into strict _key2
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
    where k.relname operator(pg_catalog.=) target_table
    and n.nspname operator(pg_catalog.=) target_schema
    ;

    -- try to grab a transaction-level advisory lock specific to the target table
    -- if we get it, no one else is building the vector index. proceed
    -- if we don't get it, someone else is already working on it. abort
    if not pg_catalog.pg_try_advisory_xact_lock(_key1, _key2) then
        raise warning 'another process is already building a vector index on %.%', target_schema, target_table;
        return;
    end if;

    -- double-check that the index doesn't exist now that we're holding the advisory lock
    -- nobody likes redundant indexes
    if ai._vectorizer_vector_index_exists(target_table, target_schema, indexing) then
        raise notice 'the vector index on %.% already exists', target_schema, target_table;
        return;
    end if;

    _implementation = pg_catalog.jsonb_extract_path_text(indexing, 'implementation');
    case _implementation
        when 'diskann' then
            select
              pg_catalog.count(*)
            , pg_catalog.string_agg
              ( case w.key
                  when 'storage_layout' then pg_catalog.format('%s=%L', w.key, w.value)
                  when 'max_alpha' then pg_catalog.format('%s=%s', w.key, w.value::pg_catalog.float8)
                  else pg_catalog.format('%s=%s', w.key, w.value::pg_catalog.int4)
                end
              , ', '
              )
            into strict
              _with_count
            , _with
            from pg_catalog.jsonb_each_text(indexing) w
            where w.key in
            ( 'storage_layout'
            , 'num_neighbors'
            , 'search_list_size'
            , 'max_alpha'
            , 'num_dimensions'
            , 'num_bits_per_dimension'
            )
            ;

            select pg_catalog.format
            ( $sql$create index on %I.%I using diskann (embedding)%s$sql$
            , target_schema, target_table
            , case when _with_count operator(pg_catalog.>) 0
                then pg_catalog.format(' with (%s)', _with)
                else ''
              end
            ) into strict _sql;
            execute _sql;
        when 'hnsw' then
            select
              pg_catalog.count(*)
            , pg_catalog.string_agg(pg_catalog.format('%s=%s', w.key, w.value::pg_catalog.int4), ', ')
            into strict
              _with_count
            , _with
            from pg_catalog.jsonb_each_text(indexing) w
            where w.key in ('m', 'ef_construction')
            ;

            select n.nspname into strict _ext_schema
            from pg_catalog.pg_extension x
            inner join pg_catalog.pg_namespace n on (x.extnamespace operator(pg_catalog.=) n.oid)
            where x.extname operator(pg_catalog.=) 'vector'
            ;

            select pg_catalog.format
            ( $sql$create index on %I.%I using hnsw (embedding %I.%s)%s$sql$
            , target_schema, target_table
            , _ext_schema
            , indexing operator(pg_catalog.->>) 'opclass'
            , case when _with_count operator(pg_catalog.>) 0
                then pg_catalog.format(' with (%s)', _with)
                else ''
              end
            ) into strict _sql;
            execute _sql;
        else
            raise exception 'unrecognized index implementation: %s', _implementation;
    end case;
end
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_job
create or replace procedure ai._vectorizer_job
( job_id pg_catalog.int4 default null
, config pg_catalog.jsonb default null
) as
$func$
declare
    _vectorizer_id pg_catalog.int4;
    _vec ai.vectorizer%rowtype;
    _sql pg_catalog.text;
    _found pg_catalog.bool;
    _count pg_catalog.int8;
begin
    set local search_path = pg_catalog, pg_temp;
    if config is null then
        raise exception 'config is null';
    end if;

    -- get the vectorizer id from the config
    select pg_catalog.jsonb_extract_path_text(config, 'vectorizer_id')::pg_catalog.int4
    into strict _vectorizer_id
    ;

    -- get the vectorizer
    select * into strict _vec
    from ai.vectorizer v
    where v.id operator(pg_catalog.=) _vectorizer_id
    ;

    commit;
    set local search_path = pg_catalog, pg_temp;

    -- if the conditions are right, create the vectorizer index
    if ai._vectorizer_should_create_vector_index(_vec) then
        commit;
        set local search_path = pg_catalog, pg_temp;
        perform ai._vectorizer_create_vector_index
        (_vec.target_schema
        , _vec.target_table
        , pg_catalog.jsonb_extract_path(_vec.config, 'indexing')
        );
    end if;

    commit;
    set local search_path = pg_catalog, pg_temp;

    -- if there is at least one item in the queue, we need to execute the vectorizer
    select pg_catalog.format
    ( $sql$
    select true
    from %I.%I
    for update skip locked
    limit 1
    $sql$
    , _vec.queue_schema, _vec.queue_table
    ) into strict _sql
    ;
    execute _sql into _found;
    commit;
    set local search_path = pg_catalog, pg_temp;
    if coalesce(_found, false) is true then
        -- count total items in the queue
        select pg_catalog.format
        ( $sql$select pg_catalog.count(1) from (select 1 from %I.%I limit 501) $sql$
        , _vec.queue_schema, _vec.queue_table
        ) into strict _sql
        ;
        execute _sql into strict _count;
        commit;
        set local search_path = pg_catalog, pg_temp;
        -- for every 50 items in the queue, execute a vectorizer max out at 10 vectorizers
        _count = least(pg_catalog.ceil(_count::pg_catalog.float8 / 50.0::pg_catalog.float8), 10::pg_catalog.float8)::pg_catalog.int8;
        raise debug 'job_id %: executing % vectorizers...', job_id, _count;
        while _count > 0 loop
            -- execute the vectorizer
            perform ai.execute_vectorizer(_vectorizer_id);
            _count = _count - 1;
        end loop;
    end if;
    commit;
    set local search_path = pg_catalog, pg_temp;
end
$func$
language plpgsql security invoker
;

-------------------------------------------------------------------------------
-- _vectorizer_schedule_job
create or replace function ai._vectorizer_schedule_job
( vectorizer_id pg_catalog.int4
, scheduling pg_catalog.jsonb
) returns pg_catalog.int8 as
$func$
declare
    _implementation pg_catalog.text;
    _sql pg_catalog.text;
    _extension_schema pg_catalog.name;
    _job_id pg_catalog.int8;
begin
    select pg_catalog.jsonb_extract_path_text(scheduling, 'implementation')
    into strict _implementation
    ;
    case
        when _implementation operator(pg_catalog.=) 'timescaledb' then
            -- look up schema/name of the extension for scheduling. may be null
            select n.nspname into _extension_schema
            from pg_catalog.pg_extension x
            inner join pg_catalog.pg_namespace n on (x.extnamespace operator(pg_catalog.=) n.oid)
            where x.extname operator(pg_catalog.=) _implementation
            ;
            if _extension_schema is null then
                raise exception 'timescaledb extension not found';
            end if;
        when _implementation operator(pg_catalog.=) 'none' then
            return null;
        else
            raise exception 'scheduling implementation not recognized';
    end case;

    -- schedule the job using the implementation chosen
    case _implementation
        when 'timescaledb' then
            -- schedule the work proc with timescaledb background jobs
            select pg_catalog.format
            ( $$select %I.add_job('ai._vectorizer_job'::pg_catalog.regproc, %s, config=>%L)$$
            , _extension_schema
            , ( -- gather up the arguments
                select pg_catalog.string_agg
                ( pg_catalog.format('%s=>%L', s.key, s.value)
                , ', '
                order by x.ord
                )
                from pg_catalog.jsonb_each_text(scheduling) s
                inner join
                pg_catalog.unnest(array['schedule_interval', 'initial_start', 'fixed_schedule', 'timezone']) with ordinality x(key, ord)
                on (s.key = x.key)
              )
            , pg_catalog.jsonb_build_object('vectorizer_id', vectorizer_id)::pg_catalog.text
            ) into strict _sql
            ;
            execute _sql into strict _job_id;
    end case;
    return _job_id;
end
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_handle_drops
create or replace function ai._vectorizer_handle_drops()
returns event_trigger as
$func$
declare
    _id int;
begin
    -- this function is security definer
    -- fully-qualify everything and be careful of security holes
    for _id in
    (
        select distinct v.id
        from pg_catalog.pg_event_trigger_dropped_objects() d
        inner join ai.vectorizer v
        on ((d.schema_name, d.object_name) in
            ( (v.source_schema, v.source_table)
            , (v.target_schema, v.target_table)
            , (v.queue_schema, v.queue_table)
            )
        )
        where pg_catalog.lower(d.object_type) operator(pg_catalog.=) 'table'
    )
    loop
        -- this may cause recursive invocations of this event trigger
        -- however it does not cause a problem
        raise notice 'associated table for vectorizer % dropped. dropping vectorizer', _id;
        perform ai.drop_vectorizer(_id);
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
    where g.evtname operator(pg_catalog.=) '_vectorizer_handle_drops'
    and g.evtfoid operator(pg_catalog.=) pg_catalog.to_regproc('ai._vectorizer_handle_drops')
    ;
    if found then
        return;
    end if;

    create event trigger _vectorizer_handle_drops
    on sql_drop
    execute function ai._vectorizer_handle_drops();
end
$block$;
