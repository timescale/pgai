

-------------------------------------------------------------------------------
-- execute_vectorizer
create or replace function ai.execute_async_ext_vectorizer(vectorizer_id int) returns void
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.vectorizer
    ai.vectorizer.execute_async_ext_vectorizer(plpy, vectorizer_id)
$python$
language plpython3u volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- indexing_none
create or replace function ai.indexing_none() returns jsonb
as $func$
    select jsonb_build_object('implementation', 'none')
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- indexing_diskann
create or replace function ai.indexing_diskann
( min_rows int default 100000
, storage_layout text default null
, num_neighbors int default null
, search_list_size int default null
, max_alpha float8 default null
, num_dimensions int default null
, num_bits_per_dimension int default null
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'diskann'
    , 'min_rows': min_rows
    , 'storage_layout': storage_layout
    , 'num_neighbors': num_neighbors
    , 'search_list_size': search_list_size
    , 'max_alpha': max_alpha
    , 'num_dimensions': num_dimensions
    , 'num_bits_per_dimension': num_bits_per_dimension
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_indexing_diskann
create or replace function ai._validate_indexing_diskann(config jsonb) returns void
as $func$
declare
    _storage_layout text;
begin
    _storage_layout = config operator(pg_catalog.->>) 'storage_layout';
    if _storage_layout is not null and not (_storage_layout operator(pg_catalog.=) any(array['memory_optimized', 'plain'])) then
        raise exception 'invalid storage_layout';
    end if;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- indexing_hnsw
create or replace function ai.indexing_hnsw
( min_rows int default 100000
, opclass text default null
, m int default null
, ef_construction int default null
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'hnsw'
    , 'min_rows': min_rows
    , 'opclass': opclass
    , 'm': m
    , 'ef_construction': ef_construction
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_indexing_hnsw
create or replace function ai._validate_indexing_hnsw(config jsonb) returns void
as $func$
declare
    _opclass text;
begin
    _opclass = config operator(pg_catalog.->>) 'opclass';
    if _opclass is not null
    and not (_opclass operator(pg_catalog.=) any(array['vector_ip_ops', 'vector_cosine_ops', 'vector_l1_ops'])) then
        raise exception 'invalid opclass';
    end if;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_indexing
create or replace function ai._validate_indexing(config jsonb) returns void
as $func$
declare
    _implementation text;
begin
    _implementation = config operator(pg_catalog.->>) 'implementation';
    case _implementation
        when 'none' then
            -- ok
        when 'diskann' then
            perform ai._validate_indexing_diskann(config);
        when 'hnsw' then
            perform ai._validate_indexing_hnsw(config);
        else
            if _implementation is null then
                raise exception 'indexing implementation not specified';
            else
                raise exception 'invalid indexing implementation: "%"', _implementation;
            end if;
    end case;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- embedding_openai
create or replace function ai.embedding_openai
( model text
, dimensions int
, "user" text default null
, api_key_name text default 'OPENAI_API_KEY'
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'openai'
    , 'model': model
    , 'dimensions': dimensions
    , 'user': "user"
    , 'api_key_name': api_key_name
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- chunking_character_text_splitter
create or replace function ai.chunking_character_text_splitter
( chunk_column name
, chunk_size int
, chunk_overlap int
, separator text default E'\n\n'
, is_separator_regex bool default false
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'character_text_splitter'
    , 'chunk_column': chunk_column
    , 'chunk_size': chunk_size
    , 'chunk_overlap': chunk_overlap
    , 'separator': separator
    , 'is_separator_regex': is_separator_regex
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_chunking_character_text_splitter
create or replace function ai._validate_chunking_character_text_splitter
( config jsonb
, source_schema name
, source_table name
) returns void
as $func$
declare
    _chunk_column text;
    _found bool;
begin
    select config operator(pg_catalog.->>) 'chunk_column'
    into strict _chunk_column
    ;

    select count(*) > 0 into strict _found
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace = n.oid)
    inner join pg_catalog.pg_attribute a on (k.oid = a.attrelid)
    where n.nspname operator(pg_catalog.=) source_schema
    and k.relname operator(pg_catalog.=) source_table
    and a.attnum operator(pg_catalog.>) 0
    and a.attname operator(pg_catalog.=) _chunk_column
    ;
    if not _found then
        raise exception 'chunk column in config does not exist in the table: %', _chunk_column;
    end if;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- formatting_python_template
create or replace function ai.formatting_python_template
( template text default '$chunk'
, columns name[] default null
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'python_template'
    , 'columns': columns
    , 'template': template
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_formatting_python_template
create or replace function ai._validate_formatting_python_template
( config jsonb
, source_schema name
, source_table name
) returns jsonb
as $func$
declare
    _template text;
    _found bool;
    _columns name[];
    _msg text;
begin
    select config operator(pg_catalog.->>) 'template'
    into strict _template
    ;
    if not pg_catalog.like(_template, '%$chunk%') then
        raise exception 'template must contain $chunk placeholder';
    end if;

    -- list the columns on the source table
    select array_agg(a.attname) into strict _columns
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace = n.oid)
    inner join pg_catalog.pg_attribute a on (k.oid = a.attrelid)
    where n.nspname operator(pg_catalog.=) source_schema
    and k.relname operator(pg_catalog.=) source_table
    and a.attnum operator(pg_catalog.>) 0
    ;
    if not found or pg_catalog.array_length(_columns, 1) operator(pg_catalog.=) 0 then
        raise exception 'source table not found';
    end if;

    -- make sure no source column is named "chunk"
    select 'chunk' = any(_columns) into strict _found;
    if _found then
        raise exception 'formatting_python_template may not be used when source table has a column named "chunk"';
    end if;

    -- if the user didn't specify a list of columns, use ALL columns
    -- otherwise, check that the columns specified actually exist
    if config operator(pg_catalog.->) 'columns' is null then
        select pg_catalog.jsonb_set
        ( config
        , array['columns']
        , pg_catalog.to_jsonb(_columns)
        , create_if_missing=>true
        ) into strict config
        ;
    else
        -- ensure the the columns listed in the config exist in the table
        -- find the columns in the config that do NOT exist in the table. hoping for zero results
        select pg_catalog.array_agg(x.x) into _columns
        from
        (
            select x
            from pg_catalog.jsonb_array_elements_text(config operator(pg_catalog.->) 'columns') x
            except
            select a.attname
            from pg_catalog.pg_class k
            inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
            inner join pg_catalog.pg_attribute a on (k.oid operator(pg_catalog.=) a.attrelid)
            where n.nspname operator(pg_catalog.=) source_schema
            and k.relname operator(pg_catalog.=) source_table
            and a.attnum operator(pg_catalog.>) 0
        ) x
        ;
        if found and _columns is not null and pg_catalog.array_length(_columns, 1) operator(pg_catalog.>) 0 then
            select pg_catalog.string_agg(x, ', ')
            into strict _msg
            from pg_catalog.unnest(_columns) x
            ;
            raise exception 'columns in config do not exist in the table: %', _msg;
        end if;
    end if;

    return config;
end
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- scheduling_none
create or replace function ai.scheduling_none() returns jsonb
as $func$
    select pg_catalog.jsonb_build_object('implementation', 'none')
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- scheduling_pg_cron
create or replace function ai.scheduling_pg_cron
( schedule text default '*/10 * * * *'
) returns jsonb
as $func$
    select pg_catalog.jsonb_build_object
    ( 'implementation', 'pg_cron'
    , 'schedule', schedule
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- scheduling_timescaledb
create or replace function ai.scheduling_timescaledb
( schedule_interval interval default interval '10m'
, initial_start timestamptz default null
, fixed_schedule bool default null
, timezone text default null
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'timescaledb'
    , 'schedule_interval': schedule_interval
    , 'initial_start': initial_start
    , 'fixed_schedule': fixed_schedule
    , 'timezone': timezone
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

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
-- _vectorizer_create_target_table
create or replace function ai._vectorizer_create_target_table
( source_schema name
, source_table name
, source_pk jsonb
, target_schema name
, target_table name
, dimensions int
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
    , s.*
    from %I.%I t
    left outer join %I.%I s
    on (%s)
    $sql$
    , view_schema, view_name
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
    , source_schema, trigger_name
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
    , source_schema, trigger_name
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
create or replace procedure ai._vectorizer_async_ext_job
( job_id int default null
, config jsonb default null
) as
$func$
declare
    _vectorizer_id int;
    _queue_schema name;
    _queue_table name;
    _sql text;
    _item record;
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
    select *
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
    perform ai.execute_async_ext_vectorizer(_vectorizer_id);
    commit;
end
$func$
language plpgsql security invoker
;

-------------------------------------------------------------------------------
-- _vectorizer_schedule_async_ext_job
create or replace function ai._vectorizer_schedule_async_ext_job
( vectorizer_id int
, scheduling jsonb
) returns bigint as
$func$
declare
    _implementation text;
    _sql text;
    _extension_schema name;
    _job_id bigint;
begin
    select pg_catalog.jsonb_extract_path_text(scheduling, 'implementation')
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
            ( $$select %I.schedule(%L, %L, $sql$call ai._vectorizer_async_ext_job(null, %L))$sql$)$$
            , _extension_schema
            , pg_catalog.jsonb_extract_path_text(scheduling, 'schedule')
            , vectorizer_id
            , pg_catalog.jsonb_build_object('vectorizer_id', vectorizer_id)::text
            ) into strict _sql
            ;
            execute _sql into strict _job_id;
        when 'timescaledb' then
            -- schedule the work proc with timescaledb background jobs
            select pg_catalog.format
            ( $$select %I.add_job('ai._vectorizer_async_ext_job'::regproc, %s, config=>%L)$$
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

-------------------------------------------------------------------------------
-- create_vectorizer
create or replace function ai.create_vectorizer
( source regclass
, embedding jsonb
, chunking jsonb
, indexing jsonb default ai.indexing_diskann()
, formatting jsonb default ai.formatting_python_template()
, scheduling jsonb default ai.scheduling_timescaledb()
, asynchronous bool default true -- TODO: remove?
, external bool default true -- TODO: remove?
, target_schema name default null
, target_table name default null
, view_schema name default null
, view_name name default null
, queue_schema name default null
, queue_table name default null
, grant_to name[] default array['vectorizer'] -- TODO: what is the final role name we want to use here?
) returns int
as $func$
declare
    _found bool;
    _source_table name;
    _source_schema name;
    _trigger_name name;
    _is_owner bool;
    _dimensions int;
    _source_pk jsonb;
    _vectorizer_id int;
    _sql text;
    _job_id bigint;
begin
    if asynchronous and not external then
        raise exception 'asynchronous internal vectorizers are not implemented yet';
    end if;

    if not asynchronous and not external then
        raise exception 'synchronous internal vectorizers are not implemented yet';
    end if;

    if not asynchronous and external then
        raise exception 'synchronous vectorizers must be internal';
    end if;

    -- make sure all the roles listed in _grant_to exist
    if grant_to is not null then
        -- do any roles NOT exist
        select pg_catalog.count(*) filter (where pg_catalog.to_regrole(r) is null) operator(pg_catalog.>) 0
        into strict _found
        from pg_catalog.unnest(grant_to) r
        ;
        if _found then
            raise exception 'one or more _grant_to roles do not exist';
        end if;
    end if;

    -- get source table name and schema name
    select k.relname, n.nspname, k.relowner operator(pg_catalog.=) current_user::regrole
    into strict _source_table, _source_schema, _is_owner
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
    where k.oid operator(pg_catalog.=) source
    ;
    -- TODO: consider allowing (in)direct members of the role that owns the source table
    if not _is_owner then
        raise exception 'only the owner of the source table may create a vectorizer on it';
    end if;

    select (embedding->'dimensions')::int into _dimensions;
    if _dimensions is null then
        raise exception '_dimensions argument is required';
    end if;

    -- get the source table's primary key definition
    select ai._vectorizer_source_pk(source) into strict _source_pk;
    if pg_catalog.jsonb_array_length(_source_pk) = 0 then
        raise exception 'source table must have a primary key constraint';
    end if;

    _vectorizer_id = pg_catalog.nextval('ai.vectorizer_id_seq'::pg_catalog.regclass);
    target_schema = coalesce(target_schema, _source_schema);
    target_table = coalesce(target_table, pg_catalog.concat(_source_table, '_embedding_store'));
    view_schema = coalesce(view_schema, _source_schema);
    view_name = coalesce(view_name, pg_catalog.concat(_source_table, '_embedding'));
    _trigger_name = pg_catalog.concat('vectorizer_src_trg_', _vectorizer_id);
    queue_schema = coalesce(queue_schema, 'ai');
    queue_table = coalesce(queue_table, pg_catalog.concat('_vectorizer_q_', _vectorizer_id));

    case embedding operator(pg_catalog.->>) 'implementation'
        when 'openai' then
            -- ok
        else
            raise exception 'unrecognized chunking config';
    end case;

    -- validate the chunking config
    case chunking operator(pg_catalog.->>) 'implementation'
        when 'character_text_splitter' then
            perform ai._validate_chunking_character_text_splitter
            ( chunking
            , _source_schema
            , _source_table
            );
        else
            raise exception 'unrecognized chunking config';
    end case;

    -- validate the indexing config
    perform ai._validate_indexing(indexing);

    -- validate the formatting config
    case formatting operator(pg_catalog.->>) 'implementation'
        when 'python_template' then
            formatting = ai._validate_formatting_python_template
            ( formatting
            , _source_schema
            , _source_table
            );
        else
            raise exception 'unrecognized formatting config';
    end case;

    -- validate the scheduling config
    case scheduling operator(pg_catalog.->>) 'implementation'
        when 'timescaledb' then
            -- ok
        when 'pg_cron' then
            -- ok
        when 'none' then
            -- ok
        else
            raise exception 'unrecognized scheduling config';
    end case;

    -- grant select on source table to _grant_to roles
    if grant_to is not null then
        select pg_catalog.format
        ( $sql$grant select on %I.%I to %s$sql$
        , _source_schema
        , _source_table
        , (
            select pg_catalog.string_agg(pg_catalog.quote_ident(x), ', ')
            from pg_catalog.unnest(grant_to) x
          )
        ) into strict _sql;
        execute _sql;
    end if;

    -- create the target table
    perform ai._vectorizer_create_target_table
    ( _source_schema
    , _source_table
    , _source_pk
    , target_schema
    , target_table
    , _dimensions
    );

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

    -- create queue table
    perform ai._vectorizer_create_queue_table
    ( queue_schema
    , queue_table
    , _source_pk
    );

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

    -- create trigger on source table to populate queue
    perform ai._vectorizer_create_source_trigger
    ( _trigger_name
    , queue_schema
    , queue_table
    , _source_schema
    , _source_table
    , _source_pk
    );

    -- create view
    perform ai._vectorizer_create_view
    ( view_schema
    , view_name
    , _source_schema
    , _source_table
    , _source_pk
    , target_schema
    , target_table
    );

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

    -- schedule the async ext job
    select ai._vectorizer_schedule_async_ext_job
    (_vectorizer_id
    , scheduling
    ) into _job_id
    ;
    if _job_id is not null then
        scheduling = pg_catalog.jsonb_insert(scheduling, array['job_id'], to_jsonb(_job_id));
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
    , view_schema
    , view_name
    , trigger_name
    , queue_schema
    , queue_table
    , config
    )
    values
    ( _vectorizer_id
    , asynchronous
    , external
    , _source_schema
    , _source_table
    , _source_pk
    , target_schema
    , target_table
    , view_schema
    , view_name
    , _trigger_name
    , queue_schema
    , queue_table
    , pg_catalog.jsonb_build_object
      ( 'version', '@extversion@'
      , 'embedding', embedding
      , 'chunking', chunking
      , 'indexing', indexing
      , 'formatting', formatting
      , 'scheduling', scheduling
      )
    );

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

    -- insert into queue any existing rows from source table
    select pg_catalog.format
    ( $sql$
    insert into %I.%I (%s)
    select %s
    from %I.%I x
    ;
    $sql$
    , queue_schema, queue_table
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

create or replace function ai.drop_vectorizer(vectorizer_id int) returns void
as $func$
declare
    _vec ai.vectorizer%rowtype;
    _trigger pg_catalog.pg_trigger%rowtype;
    _sql text;
begin
    -- grab the vectorizer we need to drop
    select v.* into strict _vec
    from ai.vectorizer v
    where v.id operator(pg_catalog.=) vectorizer_id
    ;

    -- look up the trigger so we can find the function/procedure backing the trigger
    select * into strict _trigger
    from pg_catalog.pg_trigger g
    where g.tgname operator(pg_catalog.=) _vec.trigger_name
    and g.tgrelid operator(pg_catalog.=) pg_catalog.format('%I.%I', _vec.source_schema, _vec.source_table)::regclass::oid
    ;

    -- drop the trigger on the source table
    select pg_catalog.format
    ( $sql$drop trigger %I on %I.%I$sql$
    , _trigger.tgname
    , _vec.source_schema
    , _vec.source_table
    ) into strict _sql
    ;
    execute _sql;

    -- drop the function/procedure backing the trigger
    select pg_catalog.format
    ( $sql$drop %s %I.%I()$sql$
    , case p.prokind when 'f' then 'function' when 'p' then 'procedure' end
    , n.nspname
    , p.proname
    ) into strict _sql
    from pg_catalog.pg_proc p
    inner join pg_catalog.pg_namespace n on (n.oid operator(pg_catalog.=) p.pronamespace)
    where p.oid operator(pg_catalog.=) _trigger.tgfoid
    ;
    execute _sql;

    -- drop the queue table
    select pg_catalog.format
    ( $sql$drop table %I.%I$sql$
    , n.nspname
    , k.relname
    ) into strict _sql
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
    where k.relname operator(pg_catalog.=) _vec.queue_table
    and n.nspname operator(pg_catalog.=) _vec.queue_schema
    ;
    execute _sql;

    -- delete the vectorizer row
    delete from ai.vectorizer v
    where v.id operator(pg_catalog.=) vectorizer_id
    ;
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

create or replace function ai.vectorizer_queue_pending(vectorizer_id int) returns bigint
as $func$
declare
    _queue_schema name;
    _queue_table name;
    _sql text;
    _queue_depth bigint;
begin
    select v.queue_schema, v.queue_table into _queue_schema, _queue_table
    from ai.vectorizer v
    where v.id operator(pg_catalog.=) vectorizer_id
    ;
    if _queue_schema is null or _queue_table is null then
        raise exception 'vectorizer has no queue table';
    end if;
    select format
    ( $sql$select count(*) from %I.%I$sql$
    , _queue_schema, _queue_table
    ) into strict _sql
    ;
    execute _sql into strict _queue_depth;
    return _queue_depth;
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

create or replace view ai.vectorizer_status as
select
  v.id
, pg_catalog.format('%I.%I', v.source_schema, v.source_table) as source_name
, pg_catalog.format('%I.%I', v.view_schema, v.view_name) as view_name
, case when v.queue_table is not null then
    ai.vectorizer_queue_pending(v.id)
  else 0
  end as pending
from ai.vectorizer v
;
