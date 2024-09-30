
-------------------------------------------------------------------------------
-- _vectorizer_source_pk
create or replace function ai._vectorizer_source_pk(source_table regclass) returns jsonb as
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
( source_schema name
, source_table name
, grant_to name[]
) returns void as
$func$
declare
    _sql text;
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
create or replace function ai._vectorizer_grant_to_vectorizer(grant_to name[]) returns void as
$func$
declare
    _sql text;
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
( source_schema name
, source_table name
, source_pk jsonb
, target_schema name
, target_table name
, dimensions int
, grant_to name[]
) returns void as
$func$
declare
    _pk_cols text;
    _sql text;
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
    , embedding @extschema:vector@.vector(%L) not null
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
( view_schema name
, view_name name
, source_schema name
, source_table name
, source_pk jsonb
, target_schema name
, target_table name
, grant_to name[]
) returns void as
$func$
declare
    _sql text;
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
        where a.attrelid operator(pg_catalog.=) pg_catalog.format('%I.%I', source_schema, source_table)::regclass::oid
        and a.attnum operator(pg_catalog.>) 0
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
-- _vectorizer_create_queue_table
create or replace function ai._vectorizer_create_queue_table
( queue_schema name
, queue_table name
, source_pk jsonb
, grant_to name[]
) returns void as
$func$
declare
    _sql text;
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
( trigger_name name
, queue_schema name
, queue_table name
, source_schema name
, source_table name
, source_pk jsonb
) returns void as
$func$
declare
    _sql text;
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
( target_schema name
, target_table name
, indexing jsonb
) returns bool as
$func$
declare
    _implementation text;
    _found bool;
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
-- _vectorizer_create_vector_index
create or replace function ai._vectorizer_create_vector_index
( target_schema name
, target_table name
, indexing jsonb
) returns void as
$func$
declare
    _implementation text;
    _with_count bigint;
    _with text[];
    _ext_schema name;
    _sql text;
begin
    _implementation = pg_catalog.jsonb_extract_path_text(indexing, 'implementation');
    case _implementation
        when 'diskann' then
            select
              pg_catalog.count(*)
            , pg_catalog.string_agg
              ( case w.key
                  when 'storage_layout' then pg_catalog.format('%s=%L', w.key, w.value)
                  when 'max_alpha' then pg_catalog.format('%s=%s', w.key, w.value::float8)
                  else pg_catalog.format('%s=%s', w.key, w.value::int)
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
            , pg_catalog.string_agg(pg_catalog.format('%s=%s', w.key, w.value::int), ', ')
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
( job_id int default null
, config jsonb default null
) as
$func$
declare
    _vectorizer_id int;
    _vec ai.vectorizer%rowtype;
    _sql text;
    _found bool;
    _count bigint;
    _indexing jsonb;
    _implementation text;
    _min_rows bigint;
begin
    set local search_path = pg_catalog, pg_temp;
    if config is null then
        raise exception 'config is null';
    end if;

    -- get the vectorizer id from the config
    select pg_catalog.jsonb_extract_path_text(config, 'vectorizer_id')::int
    into strict _vectorizer_id
    ;
    -- look up the queue table for the vectorizer
    select * into strict _vec
    from ai.vectorizer v
    where v.id operator(pg_catalog.=) _vectorizer_id
    ;
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
    if _found is not null then
        -- count total items in the queue
        select pg_catalog.format
        ( $sql$select count(1) from (select 1 from %I.%I limit 501) $sql$
        , _vec.queue_schema, _vec.queue_table
        ) into strict _sql
        ;
        execute _sql into _count;
        commit;
        set local search_path = pg_catalog, pg_temp;
        -- for every 50 items in the queue, execute a vectorizer max out at 10 vectorizers
        _count = least(pg_catalog.ceil(_count::float8 / 50.0::float8), 10::float8)::bigint;
        while _count > 0
        loop
            -- execute the vectorizer
            perform ai.execute_vectorizer(_vectorizer_id);
            _count = _count - 1;
        end loop;
    end if;
    commit;
    set local search_path = pg_catalog, pg_temp;

    -- grab the indexing config
    _indexing = pg_catalog.jsonb_extract_path(_vec.config, 'indexing');
    if _indexing is null then
        return;
    end if;

    -- grab the indexing config's implementation
    _implementation = pg_catalog.jsonb_extract_path_text(_indexing, 'implementation');
    -- if implementation is missing or none, exit
    if _implementation is null or _implementation = 'none' then
        return;
    end if;

    -- see if the index already exists. if so, exit
    if ai._vectorizer_vector_index_exists(_vec.target_schema, _vec.target_table, _indexing) then
        return;
    end if;

    -- if min_rows has a value
    _min_rows = coalesce(pg_catalog.jsonb_extract_path_text(_indexing, 'min_rows')::bigint, 0);
    if _min_rows > 0 then
        -- count the rows in the target table
        select pg_catalog.format
        ( $sql$select pg_catalog.count(*) from (select 1 from %I.%I limit %L) x$sql$
        , _vec.target_schema
        , _vec.target_table
        , _min_rows
        ) into strict _sql
        ;
        execute _sql into _count;
    end if;
    commit;
    set local search_path = pg_catalog, pg_temp;

    -- if we have met or exceeded min_rows, create the index
    if coalesce(_count, 0) >= _min_rows then
        perform ai._vectorizer_create_vector_index(_vec.target_schema, _vec.target_table, _indexing);
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
( vectorizer_id int
, scheduling jsonb
) returns bigint as
$func$
declare
    _implementation text;
    _sql text;
    _extension_schema name;
    _found bool;
    _job_id bigint;
begin
    select pg_catalog.jsonb_extract_path_text(scheduling, 'implementation')
    into strict _implementation
    ;
    case
        when _implementation = 'timescaledb' then
            -- look up schema/name of the extension for scheduling. may be null
            select n.nspname into _extension_schema
            from pg_catalog.pg_extension x
            inner join pg_catalog.pg_namespace n on (x.extnamespace operator(pg_catalog.=) n.oid)
            where x.extname operator(pg_catalog.=) _implementation
            ;
            if _extension_schema is null then
                raise exception 'timescaledb extension not found';
            end if;
        when _implementation = 'none' then
            return null;
        else
            raise exception 'scheduling implementation not recognized';
    end case;

    -- schedule the job using the implementation chosen
    case _implementation
        when 'timescaledb' then
            -- schedule the work proc with timescaledb background jobs
            select pg_catalog.format
            ( $$select %I.add_job('ai._vectorizer_job'::regproc, %s, config=>%L)$$
            , _extension_schema
            , ( -- gather up the arguments
                select string_agg
                ( pg_catalog.format('%s=>%L', s.key, s.value)
                , ', '
                order by x.ord
                )
                from pg_catalog.jsonb_each_text(scheduling) s
                inner join
                unnest(array['schedule_interval', 'initial_start', 'fixed_schedule', 'timezone']) with ordinality x(key, ord)
                on (s.key = x.key)
              )
            , pg_catalog.jsonb_build_object('vectorizer_id', vectorizer_id)::text
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
