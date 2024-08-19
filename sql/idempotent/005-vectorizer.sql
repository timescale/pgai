

-------------------------------------------------------------------------------
-- execute_vectorizer
create or replace function ai.execute_async_ext_vectorizer(_vectorizer_id int) returns void
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.vectorizer
    ai.vectorizer.execute_async_ext_vectorizer(plpy, _vectorizer_id)
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- embedding_config_openai
create or replace function ai.embedding_config_openai
( _model text
, _dimensions int default null
, _user text default null
) returns jsonb
as $func$
    select json_object
    ( 'provider': 'openai'
    , 'model': _model
    , 'dimensions': _dimensions
    , 'user': _user
    absent on null
    )
$func$ language sql immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- chunking_config_token_text_splitter
create or replace function ai.chunking_config_token_text_splitter
( _column name
, _chunk_size int
, _chunk_overlap int
, _separator text default ' '
) returns jsonb
as $func$
    select pg_catalog.jsonb_build_object
    ( 'implementation', 'token_text_splitter'
    , 'chunk_column', _column
    , 'chunk_size', _chunk_size
    , 'chunk_overlap', _chunk_overlap
    , 'separator', _separator
    )
$func$ language sql immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- formatting_config_python_string_template
create or replace function ai.formatting_config_python_string_template
( _columns name[]
, _template text
) returns jsonb
as $func$
    select pg_catalog.jsonb_build_object
    ( 'implementation', 'python_string_template'
    , 'columns', _columns
    , 'template', _template
    )
$func$ language sql immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- scheduling_config_none
create or replace function ai.scheduling_config_none() returns jsonb
as $func$
    select pg_catalog.jsonb_build_object('implementation', 'none')
$func$ language sql immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- scheduling_config_pg_cron
create or replace function ai.scheduling_config_pg_cron(_schedule text) returns jsonb
as $func$
    select pg_catalog.jsonb_build_object
    ( 'implementation', 'pg_cron'
    , 'schedule', _schedule
    )
$func$ language sql immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- scheduling_config_timescaledb
create or replace function ai.scheduling_config_timescaledb
( _schedule_interval interval
, _initial_start timestamptz default null
, _fixed_schedule bool default null
, _timezone text default null
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'timescaledb'
    , 'schedule_interval': _schedule_interval
    , 'initial_start': _initial_start
    , 'fixed_schedule': _fixed_schedule
    , 'timezone': _timezone
    absent on null
    )
$func$ language sql immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_source_pk
create or replace function ai._vectorizer_source_pk(_source_table regclass) returns jsonb as
$func$
    select pg_catalog.jsonb_agg(x)
    from
    (
        select e.attnum, e.pknum, a.attname, y.typname, a.attnotnull
        from pg_catalog.pg_constraint k
        cross join lateral pg_catalog.unnest(k.conkey) with ordinality e(attnum, pknum)
        inner join pg_catalog.pg_attribute a
            on (k.conrelid operator(pg_catalog.=) a.attrelid
                and e.attnum operator(pg_catalog.=) a.attnum)
        inner join pg_catalog.pg_type y on (a.atttypid operator(pg_catalog.=) y.oid)
        where k.conrelid operator(pg_catalog.=) _source_table
        and k.contype operator(pg_catalog.=) 'p'
    ) x
$func$
language sql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_create_target_table
create or replace function ai._vectorizer_create_target_table
( _source_schema name
, _source_table name
, _source_pk jsonb
, _target_schema name
, _target_table name
, _target_column name
, _dimensions int
) returns void as
$func$
declare
    _pk_cols text;
    _sql text;
begin
    select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.pknum)
    into strict _pk_cols
    from pg_catalog.jsonb_to_recordset(_source_pk) x(pknum int, attname name)
    ;
    select pg_catalog.format
    ( $sql$
    create table %I.%I
    ( id uuid not null primary key default pg_catalog.gen_random_uuid()
    , %s
    , chunk_seq int not null
    , chunk text not null
    , %I @extschema:vector@.vector(%L) not null
    , unique (%s, chunk_seq)
    , foreign key (%s) references %I.%I (%s) on delete cascade
    )
    $sql$
    , _target_schema, _target_table
    , (
        select pg_catalog.string_agg
        (
            pg_catalog.format
            ( '%I %s %s'
            , x.attname
            , x.typname
            , case x.attnotnull when true then 'not null' else '' end
            )
            , E'\n, '
            order by x.attnum
        )
        from pg_catalog.jsonb_to_recordset(_source_pk)
            x(attnum int, attname name, typname name, attnotnull bool)
      )
    , _target_column, _dimensions
    , _pk_cols
    , _pk_cols
    , _source_schema, _source_table
    , _pk_cols
    ) into strict _sql
    ;
    execute _sql;
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_create_queue_table
create or replace function ai._vectorizer_create_queue_table
( _queue_schema name
, _queue_table name
, _source_pk jsonb
) returns void as
$func$
declare
    _sql text;
begin
    select pg_catalog.format
    ( $sql$create table %I.%I(%s, queued_at timestamptz not null default now())$sql$
    , _queue_schema, _queue_table
    , (
        select pg_catalog.string_agg
        (
          pg_catalog.format
          ( '%I %s %s'
          , x.attname
          , x.typname
          , case x.attnotnull when true then 'not null' else '' end
          )
          , E'\n, '
          order by x.attnum
        )
        from pg_catalog.jsonb_to_recordset(_source_pk) x(attnum int, attname name, typname name, attnotnull bool)
      )
    ) into strict _sql
    ;
    execute _sql;

    select pg_catalog.format
    ( $sql$create index on %I.%I (%s)$sql$
    , _queue_schema, _queue_table
    , (
        select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.pknum)
        from pg_catalog.jsonb_to_recordset(_source_pk) x(pknum int, attname name)
      )
    ) into strict _sql
    ;
    execute _sql;
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_create_source_trigger
create or replace function ai._vectorizer_create_source_trigger
( _trigger_name name
, _queue_schema name
, _queue_table name
, _source_schema name
, _source_table name
, _source_pk jsonb
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
    $plpgsql$ language plpgsql volatile parallel unsafe security invoker
    set search_path to pg_catalog, pg_temp
    $sql$
    , _source_schema, _trigger_name
    , _queue_schema, _queue_table
    , (
        select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(_source_pk) x(attnum int, attname name)
      )
    , (
        select pg_catalog.string_agg(pg_catalog.format('new.%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(_source_pk) x(attnum int, attname name)
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
    , _trigger_name
    , _source_schema, _source_table
    , _source_schema, _trigger_name
    ) into strict _sql
    ;
    execute _sql;
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_async_ext_job
create or replace function ai._vectorizer_async_ext_job(_config jsonb) returns bool as
$func$
declare
    _vectorizer_id int;
    _queue_schema name;
    _queue_table name;
    _sql text;
begin
    -- get the vectorizer id from the config
    select pg_catalog.jsonb_extract_path_text(_config, 'vectorizer_id')::int
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
    select *
    from %I.%I
    for update skip locked
    limit 1
    $sql$
    , _queue_schema, _queue_table
    ) into strict _sql
    ;
    execute _sql;
    if not found then
        -- nothing to do
        return false;
    end if;
    -- execute the vectorizer
    perform ai.execute_async_ext_vectorizer(_vectorizer_id);
    return true;
end
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_schedule_async_ext_job
create or replace function ai._vectorizer_schedule_async_ext_job
( _vectorizer_id int
, _scheduling jsonb
) returns bigint as
$func$
declare
    _implementation text;
    _sql text;
    _extension_schema name;
    _job_id bigint;
begin
    select pg_catalog.jsonb_extract_path_text(_scheduling, 'implementation')
    into strict _implementation
    ;
    case
        when _implementation in ('pg_cron', 'timescaledb') then
            -- look up schema/name of the extension for scheduling. may be null
            select n.nspname into _extension_schema
            from pg_catalog.pg_extension x
            inner join pg_catalog.pg_namespace n on (x.extnamespace operator(pg_catalog.=) n.oid)
            where x.extname operator(pg_catalog.=) _implementation
            ;
            if _extension_schema is null then
                raise exception '% extension is not found', _implementation;
            end if;
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
            ( $$select %I.schedule(%L, %L, $sql$select ai._vectorizer_async_ext_job(pg_catalog.jsonb_build_object('vectorizer_id', %L))$sql$)$$
            , _extension_schema
            , pg_catalog.jsonb_extract_path_text(_scheduling, 'schedule')
            , _vectorizer_id
            ) into strict _sql
            ;
            execute _sql into strict _job_id;
        when 'timescaledb' then
            -- schedule the work proc with timescaledb background jobs
            select pg_catalog.format
            ( $$select %I.add_job('ai._vectorizer_async_ext_job'::regproc, %s, config=>jsonb_build_object('vectorizer_id', %L))$$
            , _extension_schema
            , ( -- gather up the arguments
                select string_agg
                ( case s.key
                    when 'schedule_interval' then pg_catalog.format('%L', s.value)
                    else pg_catalog.format('%s=>%L', s.key, s.value)
                  end
                , ', '
                order by x.ord
                )
                from pg_catalog.jsonb_each_text(_scheduling) s
                inner join
                unnest(array['schedule_interval', 'initial_start', 'fixed_schedule', 'timezone']) with ordinality x(key, ord)
                on (s.key = x.key)
              )
            , _vectorizer_id
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
-- create_vectorizer
create or replace function ai.create_vectorizer
( _source regclass
, _dimensions int
, _embedding jsonb
, _chunking jsonb
, _formatting jsonb
, _scheduling jsonb
, _asynchronous bool default true
, _external bool default true
, _target_schema name default null
, _target_table name default null
, _target_column name default null
, _queue_schema name default null
, _queue_table name default null
) returns int
as $func$
declare
    _source_table name;
    _source_schema name;
    _source_pk jsonb;
    _vectorizer_id int;
    _sql text;
    _job_id bigint;
begin
    if _asynchronous and not _external then
        raise exception 'asynchronous internal vectorizers are not implemented yet';
    end if;

    if not _asynchronous and not _external then
        raise exception 'synchronous internal vectorizers are not implemented yet';
    end if;

    if not _asynchronous and _external then
        raise exception 'synchronous vectorizers must be internal';
    end if;

    -- get source table name and schema name
    select k.relname, n.nspname
    into strict _source_table, _source_schema
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
    where k.oid operator(pg_catalog.=) _source
    ;

    if _dimensions is null then
        raise exception '_dimensions argument is required';
    end if;

    -- get the source table's primary key definition
    select ai._vectorizer_source_pk(_source) into strict _source_pk;
    if pg_catalog.jsonb_array_length(_source_pk) = 0 then
        raise exception 'source table must have a primary key constraint';
    end if;

    _vectorizer_id = pg_catalog.nextval('ai.vectorizer_id_seq'::pg_catalog.regclass);
    _target_schema = coalesce(_target_schema, _source_schema);
    _target_table = coalesce(_target_table, pg_catalog.concat(_source_table, '_embedding'));
    _target_column = coalesce(_target_column, 'embedding');
    _queue_schema = coalesce(_queue_schema, 'ai');
    _queue_table = coalesce(_queue_table, pg_catalog.concat('vectorizer_q_', _vectorizer_id));

    -- create the target table
    perform ai._vectorizer_create_target_table
    ( _source_schema
    , _source_table
    , _source_pk
    , _target_schema
    , _target_table
    , _target_column
    , _dimensions
    );

    -- create queue table
    perform ai._vectorizer_create_queue_table
    ( _queue_schema
    , _queue_table
    , _source_pk
    );

    -- create trigger on source table to populate queue
    perform ai._vectorizer_create_source_trigger
    ( pg_catalog.concat('vectorizer_src_trg_', _vectorizer_id)
    , _queue_schema
    , _queue_table
    , _source_schema
    , _source_table
    , _source_pk
    );

    -- schedule the async ext job
    select ai._vectorizer_schedule_async_ext_job
    (_vectorizer_id
    , _scheduling
    ) into _job_id
    ;
    if _job_id is not null then
        _scheduling = pg_catalog.jsonb_insert(_scheduling, array['job_id'], to_jsonb(_job_id));
    end if;

    insert into ai.vectorizer
    ( id
    , asynchronous
    , external
    , source_schema
    , source_table
    , source_pk
    , target_schema
    , target_table
    , target_column
    , queue_schema
    , queue_table
    , config
    )
    values
    ( _vectorizer_id
    , _asynchronous
    , _external
    , _source_schema
    , _source_table
    , _source_pk
    , _target_schema
    , _target_table
    , _target_column
    , _queue_schema
    , _queue_table
    , pg_catalog.jsonb_build_object
      ( 'version', '@extversion@'
      , 'embedding', _embedding
      , 'chunking', _chunking
      , 'formatting', _formatting
      , 'scheduling', _scheduling
      )
    );

    -- insert into queue any existing rows from source table
    select pg_catalog.format
    ( $sql$
    insert into %I.%I (%s)
    select %s
    from %I.%I x
    ;
    $sql$
    , _queue_schema, _queue_table
    , (
        select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(_source_pk) x(attnum int, attname name)
      )
    , (
        select pg_catalog.string_agg(pg_catalog.format('x.%I', x.attname), ', ' order by x.attnum)
        from pg_catalog.jsonb_to_recordset(_source_pk) x(attnum int, attname name)
      )
    , _source_schema, _source_table
    ) into strict _sql
    ;
    execute _sql;

    return _vectorizer_id;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;
