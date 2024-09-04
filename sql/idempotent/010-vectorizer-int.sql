
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
    -- grant select on source table to _grant_to roles
    if grant_to is not null then
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
    -- grant select on vectorizer table _grant_to roles
    -- TODO: is there a better way to do this?
    if grant_to is not null then
        -- grant select on the users that do NOT already have it
        for _sql in
        (
            select pg_catalog.format($sql$grant select on ai.vectorizer to %I$sql$, x)
            from pg_catalog.unnest(grant_to) x
            where not pg_catalog.has_table_privilege
            ( x
            , 'ai.vectorizer'
            , 'select'
            )
        )
        loop
            execute _sql;
        end loop;
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

    -- grant select, insert, update on target table to _grant_to roles
    if grant_to is not null then
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

    -- grant select view to _grant_to roles
    if grant_to is not null then
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

    -- grant select, update, delete on queue table to _grant_to roles
    if grant_to is not null then
        select pg_catalog.format
        ( $sql$grant select, update, delete on %I.%I to %s$sql$
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
    select pg_catalog.format
    ( $sql$
    create function %I.%I() returns trigger
    as $plpgsql$
    begin
        insert into %I.%I (%s)
        values (%s);
        return null;
    end;
    $plpgsql$ language plpgsql volatile parallel safe security invoker
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
-- _vectorizer_job
create or replace procedure ai._vectorizer_job
( job_id int default null
, config jsonb default null
) as
$func$
declare
    _vectorizer_id int;
    _queue_schema name;
    _queue_table name;
    _sql text;
    _item bigint;
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
    select v.queue_schema, v.queue_table into strict _queue_schema, _queue_table
    from ai.vectorizer v
    where v.id operator(pg_catalog.=) _vectorizer_id
    ;
    -- if there is at least one item in the queue, we need to execute the vectorizer
    select pg_catalog.format
    ( $sql$
    select 1
    from %I.%I
    for update skip locked
    limit 1
    $sql$
    , _queue_schema, _queue_table
    ) into strict _sql
    ;
    execute _sql into _item;
    commit;
    set local search_path = pg_catalog, pg_temp;
    if _item is null then
        -- nothing to do
        return;
    end if;
    -- execute the vectorizer
    perform ai.execute_vectorizer(_vectorizer_id);
    commit;
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
        when _implementation = 'pg_cron' then
            select count(*) > 0 into strict _found
            from pg_catalog.pg_extension x
            where x.extname operator(pg_catalog.=) _implementation
            ;
            if not _found then
                raise exception 'pg_cron extension not found';
            end if;
            _extension_schema = 'cron';
        when _implementation = 'none' then
            return null;
        else
            raise exception 'scheduling implementation not recognized';
    end case;

    -- schedule the job using the implementation chosen
    case _implementation
        when 'pg_cron' then
            -- schedule the work proc with pg_cron
            select pg_catalog.format
            ( $$select %I.schedule(%L, %L, $sql$call ai._vectorizer_job(null, pg_catalog.jsonb_build_object('vectorizer_id', %s))$sql$)$$
            , _extension_schema
            , pg_catalog.concat('vectorizer_', vectorizer_id)
            , pg_catalog.jsonb_extract_path_text(scheduling, 'schedule')
            , vectorizer_id
            ) into strict _sql
            ;
            execute _sql into strict _job_id;
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
