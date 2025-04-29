-------------------------------------------------------------------------------
-- create_vectorizer
create or replace function ai.create_vectorizer
( source pg_catalog.regclass
, name pg_catalog.text default null
, destination pg_catalog.jsonb default ai.destination_table()
, loading pg_catalog.jsonb default null
, parsing pg_catalog.jsonb default ai.parsing_auto()
, embedding pg_catalog.jsonb default null
, chunking pg_catalog.jsonb default ai.chunking_recursive_character_text_splitter()
, indexing pg_catalog.jsonb default ai.indexing_default()
, formatting pg_catalog.jsonb default ai.formatting_python_template()
, scheduling pg_catalog.jsonb default ai.scheduling_default()
, processing pg_catalog.jsonb default ai.processing_default()
, queue_schema pg_catalog.name default null
, queue_table pg_catalog.name default null
, grant_to pg_catalog.name[] default ai.grant_to()
, enqueue_existing pg_catalog.bool default true
, if_not_exists pg_catalog.bool default false
) returns pg_catalog.int4
as $func$
declare
    _missing_roles pg_catalog.name[];
    _source_table pg_catalog.name;
    _source_schema pg_catalog.name;
    _trigger_name pg_catalog.name;
    _is_owner pg_catalog.bool;
    _dimensions pg_catalog.int4;
    _source_pk pg_catalog.jsonb;
    _vectorizer_id pg_catalog.int4;
    _existing_vectorizer_id pg_catalog.int4;
    _sql pg_catalog.text;
    _job_id pg_catalog.int8;
    _queue_failed_table pg_catalog.name;
begin
    -- make sure all the roles listed in grant_to exist
    if grant_to is not null then
        select
          pg_catalog.array_agg(r) filter (where r operator(pg_catalog.!=) 'public' and pg_catalog.to_regrole(r) is null) -- missing
        , pg_catalog.array_agg(r) filter (where r operator(pg_catalog.=) 'public' or pg_catalog.to_regrole(r) is not null) -- real roles
        into strict
          _missing_roles
        , grant_to
        from pg_catalog.unnest(grant_to) r
        ;
        if pg_catalog.array_length(_missing_roles, 1) operator(pg_catalog.>) 0 then
            raise warning 'one or more grant_to roles do not exist: %', _missing_roles;
        end if;
    end if;

    if embedding is null then
        raise exception 'embedding configuration is required';
    end if;
    
    if loading is null then
        raise exception 'loading configuration is required';
    end if;

    -- get source table name and schema name
    select
      k.relname
    , n.nspname
    , pg_catalog.pg_has_role(pg_catalog.current_user(), k.relowner, 'MEMBER')
    into strict _source_table, _source_schema, _is_owner
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
    where k.oid operator(pg_catalog.=) source
    ;
    -- not an owner of the table, but superuser?
    if not _is_owner then
        select r.rolsuper into strict _is_owner
        from pg_catalog.pg_roles r
        where r.rolname operator(pg_catalog.=) pg_catalog.current_user()
        ;
    end if;

    if not _is_owner then
        raise exception 'only a superuser or the owner of the source table may create a vectorizer on it';
    end if;

    select (embedding operator(pg_catalog.->) 'dimensions')::pg_catalog.int4 into _dimensions;
    if _dimensions is null then
        raise exception 'dimensions argument is required';
    end if;

    -- get the source table's primary key definition
    select ai._vectorizer_source_pk(source) into strict _source_pk;
    if _source_pk is null or pg_catalog.jsonb_array_length(_source_pk) operator(pg_catalog.=) 0 then
        raise exception 'source table must have a primary key constraint';
    end if;

    _vectorizer_id = pg_catalog.nextval('ai.vectorizer_id_seq'::pg_catalog.regclass);
    _trigger_name = pg_catalog.concat('_vectorizer_src_trg_', _vectorizer_id);
    queue_schema = coalesce(queue_schema, 'ai');
    queue_table = coalesce(queue_table, pg_catalog.concat('_vectorizer_q_', _vectorizer_id));
    _queue_failed_table = pg_catalog.concat('_vectorizer_q_failed_', _vectorizer_id);

    -- make sure queue table name is available
    if pg_catalog.to_regclass(pg_catalog.format('%I.%I', queue_schema, queue_table)) is not null then
        raise exception 'an object named %.% already exists. specify an alternate queue_table explicitly', queue_schema, queue_table
        using errcode = 'duplicate_object';
    end if;

    -- validate the loading config
    perform ai._validate_loading(loading, _source_schema, _source_table);

    -- validate the parsing config
    perform ai._validate_parsing(
        parsing,
        loading,
        _source_schema,
        _source_table
    );

    -- validate the destination config
    perform ai._validate_destination(destination, chunking);

    -- validate the embedding config
    perform ai._validate_embedding(embedding);

    -- validate the chunking config
    perform ai._validate_chunking(chunking);

    -- if ai.indexing_default, resolve the default
    if indexing operator(pg_catalog.->>) 'implementation' = 'default' then
        indexing = ai._resolve_indexing_default();
    end if;

    -- validate the indexing config
    perform ai._validate_indexing(indexing);

    -- validate the formatting config
    perform ai._validate_formatting(formatting, _source_schema, _source_table);

    -- if ai.scheduling_default, resolve the default
    if scheduling operator(pg_catalog.->>) 'implementation' = 'default' then
        scheduling = ai._resolve_scheduling_default();
    end if;

    -- validate the scheduling config
    perform ai._validate_scheduling(scheduling);

    -- validate the processing config
    perform ai._validate_processing(processing);

    -- if scheduling is none then indexing must also be none
    if scheduling operator(pg_catalog.->>) 'implementation' = 'none'
    and indexing operator(pg_catalog.->>) 'implementation' != 'none' then
        raise exception 'automatic indexing is not supported without scheduling. set indexing=>ai.indexing_none() when scheduling=>ai.scheduling_none()';
    end if;

    -- evaluate the destination config
    destination = ai._evaluate_destination(destination, _source_schema, _source_table);

    if name is null then
        if destination operator(pg_catalog.->>) 'implementation' = 'table' then
            name = pg_catalog.format('%s_%s', destination operator(pg_catalog.->>) 'target_schema', destination operator(pg_catalog.->>) 'target_table');
        elseif destination operator(pg_catalog.->>) 'implementation' = 'column' then
            name = pg_catalog.format('%s_%s_%s', _source_schema, _source_table, destination operator(pg_catalog.->>) 'embedding_column');
        end if;
    end if;

    -- validate the name is available
    select id from ai.vectorizer
    where ai.vectorizer.name operator(pg_catalog.=) create_vectorizer.name
    into _existing_vectorizer_id
    ;
    if _existing_vectorizer_id is not null then
        if if_not_exists is false then
            raise exception 'a vectorizer named % already exists.', name
            using errcode = 'duplicate_object';
        end if;
        raise notice 'a vectorizer named % already exists, skipping', name;
        return _existing_vectorizer_id;
    end if;
    
    -- validate the destination can create objects after the if_not_exists check
    perform ai._validate_destination_can_create_objects(destination);

    -- grant select to source table
    perform ai._vectorizer_grant_to_source
    ( _source_schema
    , _source_table
    , grant_to
    );

    -- create the target table or column
    if destination operator(pg_catalog.->>) 'implementation' = 'table' then
        perform ai._vectorizer_create_destination_table
        ( _source_schema
        , _source_table
        , _source_pk
        , _dimensions
        , destination
        , grant_to
        );
    elseif destination operator(pg_catalog.->>) 'implementation' = 'column' then
        perform ai._vectorizer_create_destination_column
        ( _source_schema
        , _source_table
        , _dimensions
        , destination
        );
    else
        raise exception 'invalid implementation for destination';
    end if;

    -- create queue table
    perform ai._vectorizer_create_queue_table
    ( queue_schema
    , queue_table
    , _source_pk
    , grant_to
    );

    -- create queue failed table
    perform ai._vectorizer_create_queue_failed_table
    ( queue_schema
    , _queue_failed_table
    , _source_pk
    , grant_to
    );

    -- create trigger on source table to populate queue
    perform ai._vectorizer_create_source_trigger
    ( _trigger_name
    , queue_schema
    , queue_table
    , _source_schema
    , _source_table
    , destination operator(pg_catalog.->>) 'target_schema'
    , destination operator(pg_catalog.->>) 'target_table'
    , _source_pk
    );


    -- schedule the async ext job
    select ai._vectorizer_schedule_job
    (_vectorizer_id
    , scheduling
    ) into _job_id
    ;
    if _job_id is not null then
        scheduling = pg_catalog.jsonb_insert(scheduling, array['job_id'], pg_catalog.to_jsonb(_job_id));
    end if;

    insert into ai.vectorizer
    ( id
    , source_schema
    , source_table
    , source_pk
    , trigger_name
    , queue_schema
    , queue_table
    , queue_failed_table
    , config
    , name
    )
    values
    ( _vectorizer_id
    , _source_schema
    , _source_table
    , _source_pk
    , _trigger_name
    , queue_schema
    , queue_table
    , _queue_failed_table
    , pg_catalog.jsonb_build_object
      ( 'version', '__version__'
      , 'loading', loading
      , 'parsing', parsing
      , 'embedding', embedding
      , 'chunking', chunking
      , 'indexing', indexing
      , 'formatting', formatting
      , 'scheduling', scheduling
      , 'processing', processing
      , 'destination', destination
      )
    , create_vectorizer.name
    );

    -- grant select on the vectorizer table
    perform ai._vectorizer_grant_to_vectorizer(grant_to);

    -- insert into queue any existing rows from source table
    if enqueue_existing is true then
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
    end if;
    return _vectorizer_id;
end
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- disable_vectorizer_schedule
create or replace function ai.disable_vectorizer_schedule(vectorizer_id pg_catalog.int4) returns void
as $func$
declare
    _vec ai.vectorizer%rowtype;
    _schedule pg_catalog.jsonb;
    _job_id pg_catalog.int8;
    _sql pg_catalog.text;
begin
    update ai.vectorizer v
    set disabled = true
    where v.id operator(pg_catalog.=) vectorizer_id
    returning * into strict _vec
    ;

    -- enable the scheduled job if exists
    _schedule = _vec.config operator(pg_catalog.->) 'scheduling';
    if _schedule is not null then
        case _schedule operator(pg_catalog.->>) 'implementation'
            when 'none' then -- ok
            when 'timescaledb' then
                _job_id = (_schedule operator(pg_catalog.->) 'job_id')::pg_catalog.int8;
                select pg_catalog.format
                ( $$select %I.alter_job(job_id, scheduled=>false) from timescaledb_information.jobs where job_id = %L$$
                , n.nspname
                , _job_id
                ) into _sql
                from pg_catalog.pg_extension x
                inner join pg_catalog.pg_namespace n on (x.extnamespace = n.oid)
                where x.extname = 'timescaledb'
                ;
                if _sql is not null then
                    execute _sql;
                end if;
        end case;
    end if;
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

create or replace function ai.disable_vectorizer_schedule(name pg_catalog.text) returns void
as $func$
   select ai.disable_vectorizer_schedule(v.id)
   from ai.vectorizer v
   where v.name operator(pg_catalog.=) disable_vectorizer_schedule.name;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- enable_vectorizer_schedule
create or replace function ai.enable_vectorizer_schedule(vectorizer_id pg_catalog.int4) returns void
as $func$
declare
    _vec ai.vectorizer%rowtype;
    _schedule pg_catalog.jsonb;
    _job_id pg_catalog.int8;
    _sql pg_catalog.text;
begin
    update ai.vectorizer v
    set disabled = false
    where v.id operator(pg_catalog.=) vectorizer_id
    returning * into strict _vec
    ;

    -- enable the scheduled job if exists
    _schedule = _vec.config operator(pg_catalog.->) 'scheduling';
    if _schedule is not null then
        case _schedule operator(pg_catalog.->>) 'implementation'
            when 'none' then -- ok
            when 'timescaledb' then
                _job_id = (_schedule operator(pg_catalog.->) 'job_id')::pg_catalog.int8;
                select pg_catalog.format
                ( $$select %I.alter_job(job_id, scheduled=>true) from timescaledb_information.jobs where job_id = %L$$
                , n.nspname
                , _job_id
                ) into _sql
                from pg_catalog.pg_extension x
                inner join pg_catalog.pg_namespace n on (x.extnamespace operator(pg_catalog.=) n.oid)
                where x.extname operator(pg_catalog.=) 'timescaledb'
                ;
                if _sql is not null then
                    execute _sql;
                end if;
        end case;
    end if;
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

create or replace function ai.enable_vectorizer_schedule(name pg_catalog.text) returns void
as $func$
   select ai.enable_vectorizer_schedule(v.id)
   from ai.vectorizer v
   where v.name operator(pg_catalog.=) enable_vectorizer_schedule.name;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- drop_vectorizer
create or replace function ai.drop_vectorizer
( vectorizer_id pg_catalog.int4
, drop_all pg_catalog.bool default false
) returns void
as $func$
/* drop_vectorizer
This function does the following:
1. deletes the scheduled job if any
2. drops the trigger from the source table
3. drops the trigger function
4. drops the queue table
5. deletes the vectorizer row

UNLESS drop_all = true, it does NOT:
1. drop the target table containing the embeddings
2. drop the view joining the target and source
*/
declare
    _vec ai.vectorizer%rowtype;
    _schedule pg_catalog.jsonb;
    _job_id pg_catalog.int8;
    _trigger pg_catalog.pg_trigger%rowtype;
    _sql pg_catalog.text;
begin
    -- grab the vectorizer we need to drop
    select v.* into strict _vec
    from ai.vectorizer v
    where v.id operator(pg_catalog.=) vectorizer_id
    ;

    -- delete the scheduled job if exists
    _schedule = _vec.config operator(pg_catalog.->) 'scheduling';
    if _schedule is not null then
        case _schedule operator(pg_catalog.->>) 'implementation'
            when 'none' then -- ok
            when 'timescaledb' then
                _job_id = (_schedule operator(pg_catalog.->) 'job_id')::pg_catalog.int8;
                select pg_catalog.format
                ( $$select %I.delete_job(job_id) from timescaledb_information.jobs where job_id = %L$$
                , n.nspname
                , _job_id
                ) into _sql
                from pg_catalog.pg_extension x
                inner join pg_catalog.pg_namespace n on (x.extnamespace operator(pg_catalog.=) n.oid)
                where x.extname operator(pg_catalog.=) 'timescaledb'
                ;
                if found then
                    execute _sql;
                end if;
        end case;
    end if;

    -- try to look up the trigger so we can find the function/procedure backing the trigger
    select * into _trigger
    from pg_catalog.pg_trigger g
    inner join pg_catalog.pg_class k
    on (g.tgrelid operator(pg_catalog.=) k.oid
    and k.relname operator(pg_catalog.=) _vec.source_table)
    inner join pg_catalog.pg_namespace n
    on (k.relnamespace operator(pg_catalog.=) n.oid
    and n.nspname operator(pg_catalog.=) _vec.source_schema)
    where g.tgname operator(pg_catalog.=) _vec.trigger_name
    ;

    -- drop the trigger on the source table
    if found then
        select pg_catalog.format
        ( $sql$drop trigger %I on %I.%I$sql$
        , _trigger.tgname
        , _vec.source_schema
        , _vec.source_table
        ) into strict _sql
        ;
        execute _sql;

        select pg_catalog.format
        ( $sql$drop trigger if exists %I on %I.%I$sql$
        , format('%s_truncate', _trigger.tgname)
        , _vec.source_schema
        , _vec.source_table
        ) into _sql;
        execute _sql;

        -- drop the function/procedure backing the trigger
        select pg_catalog.format
        ( $sql$drop %s %I.%I()$sql$
        , case p.prokind when 'f' then 'function' when 'p' then 'procedure' end
        , n.nspname
        , p.proname
        ) into _sql
        from pg_catalog.pg_proc p
        inner join pg_catalog.pg_namespace n on (n.oid operator(pg_catalog.=) p.pronamespace)
        where p.oid operator(pg_catalog.=) _trigger.tgfoid
        ;
        if found then
            execute _sql;
        end if;
    else
        -- the trigger is missing. try to find the backing function by name and return type
        select pg_catalog.format
        ( $sql$drop %s %I.%I() cascade$sql$ -- cascade in case the trigger still exists somehow
        , case p.prokind when 'f' then 'function' when 'p' then 'procedure' end
        , n.nspname
        , p.proname
        ) into _sql
        from pg_catalog.pg_proc p
        inner join pg_catalog.pg_namespace n on (n.oid operator(pg_catalog.=) p.pronamespace)
        inner join pg_catalog.pg_type y on (p.prorettype operator(pg_catalog.=) y.oid)
        where n.nspname operator(pg_catalog.=) _vec.queue_schema
        and p.proname operator(pg_catalog.=) _vec.trigger_name
        and y.typname operator(pg_catalog.=) 'trigger'
        ;
        if found then
            execute _sql;
        end if;
    end if;

    -- drop the queue table if exists
    select pg_catalog.format
    ( $sql$drop table if exists %I.%I$sql$
    , _vec.queue_schema
    , _vec.queue_table
    ) into strict _sql;
    execute _sql;

    -- drop the failed queue table if exists
    select pg_catalog.format
    ( $sql$drop table if exists %I.%I$sql$
    , _vec.queue_schema
    , _vec.queue_failed_table
    ) into strict _sql;
    execute _sql;

    if drop_all and _vec.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'implementation' operator(pg_catalog.=) 'table' then
        -- drop the view if exists
        select pg_catalog.format
        ( $sql$drop view if exists %I.%I$sql$
        , _vec.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'view_schema'
        , _vec.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'view_name'
        ) into strict _sql;
        execute _sql;

        -- drop the target table if exists
        select pg_catalog.format
        ( $sql$drop table if exists %I.%I$sql$
        , _vec.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'target_schema'
        , _vec.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'target_table'
        ) into strict _sql;
        execute _sql;
    end if;

    -- delete the vectorizer row
    delete from ai.vectorizer v
    where v.id operator(pg_catalog.=) vectorizer_id
    ;
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

create or replace function ai.drop_vectorizer(name pg_catalog.text, drop_all pg_catalog.bool default false) returns void
as $func$
   select ai.drop_vectorizer(v.id, drop_all)
   from ai.vectorizer v
   where v.name operator(pg_catalog.=) drop_vectorizer.name;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- vectorizer_queue_pending
create or replace function ai.vectorizer_queue_pending
( vectorizer_id pg_catalog.int4
, exact_count pg_catalog.bool default false
) returns pg_catalog.int8
as $func$
declare
    _queue_schema pg_catalog.name;
    _queue_table pg_catalog.name;
    _sql pg_catalog.text;
    _queue_depth pg_catalog.int8;
begin
    select v.queue_schema, v.queue_table into _queue_schema, _queue_table
    from ai.vectorizer v
    where v.id operator(pg_catalog.=) vectorizer_id
    ;

    if _queue_schema is null or _queue_table is null then
        raise exception 'vectorizer has no queue table';
    end if;

    if exact_count then
        select format
        ( $sql$select count(1) from %I.%I$sql$
        , _queue_schema, _queue_table
        ) into strict _sql
        ;
        execute _sql into strict _queue_depth;
    else
        select format
        ( $sql$select count(*) from (select 1 from %I.%I limit 10001) as subselect$sql$
        , _queue_schema, _queue_table
        ) into strict _sql
        ;
        execute _sql into strict _queue_depth;
        if _queue_depth operator(pg_catalog.=) 10001 then
            _queue_depth = 9223372036854775807; -- max bigint value
        end if;
    end if;

    return _queue_depth;
end;
$func$ language plpgsql stable security invoker
set search_path to pg_catalog, pg_temp
;

create or replace function ai.vectorizer_queue_pending
( name pg_catalog.text
, exact_count pg_catalog.bool default false
) returns pg_catalog.int8
as $func$
   select ai.vectorizer_queue_pending(v.id, exact_count)
   from ai.vectorizer v
   where v.name operator(pg_catalog.=) vectorizer_queue_pending.name;
$func$ language sql stable security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- vectorizer_status
create or replace view ai.vectorizer_status as
select
  v.id
, pg_catalog.format('%I.%I', v.source_schema, v.source_table) as source_table
, case when v.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'implementation' = 'table' then
    pg_catalog.format('%I.%I', v.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'target_schema', v.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'target_table')
    else null
    end as target_table
, case when v.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'implementation' = 'table' then
    pg_catalog.format('%I.%I', v.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'view_schema', v.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'view_name')
    else null
    end as "view"
, case when v.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'implementation' = 'column' then
    pg_catalog.format('%I', v.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'embedding_column')
    else 'embedding'
    end as embedding_column
, case when v.queue_table is not null and
    pg_catalog.has_table_privilege
    ( current_user
    , pg_catalog.format('%I.%I', v.queue_schema, v.queue_table)
    , 'select'
    )
    then ai.vectorizer_queue_pending(v.id)
  else null
  end as pending_items
, disabled
from ai.vectorizer v
;

-------------------------------------------------------------------------------
-- vectorizer_embed
create or replace function ai.vectorizer_embed
( embedding_config pg_catalog.jsonb
, input_text pg_catalog.text
, input_type pg_catalog.text default null
) returns @extschema:vector@.vector
as $func$
declare
    _emb @extschema:vector@.vector;
begin
    case embedding_config operator(pg_catalog.->>) 'implementation'
        when 'openai' then
            _emb = ai.openai_embed
            ( embedding_config operator(pg_catalog.->>) 'model'
            , input_text
            , api_key_name=>(embedding_config operator(pg_catalog.->>) 'api_key_name')
            , dimensions=>(embedding_config operator(pg_catalog.->>) 'dimensions')::pg_catalog.int4
            , openai_user=>(embedding_config operator(pg_catalog.->>) 'user')
            );
        when 'ollama' then
            _emb = ai.ollama_embed
            ( embedding_config operator(pg_catalog.->>) 'model'
            , input_text
            , host=>(embedding_config operator(pg_catalog.->>) 'base_url')
            , keep_alive=>(embedding_config operator(pg_catalog.->>) 'keep_alive')
            , embedding_options=>(embedding_config operator(pg_catalog.->) 'options')
            );
        when 'voyageai' then
            _emb = ai.voyageai_embed
            ( embedding_config operator(pg_catalog.->>) 'model'
            , input_text
            , input_type=>coalesce(input_type, 'query')
            , api_key_name=>(embedding_config operator(pg_catalog.->>) 'api_key_name')
            );
        else
            raise exception 'unsupported embedding implementation';
    end case;

    return _emb;
end
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- vectorizer_embed
create or replace function ai.vectorizer_embed
( vectorizer_id pg_catalog.int4
, input_text pg_catalog.text
, input_type pg_catalog.text default null
) returns @extschema:vector@.vector
as $func$
    select ai.vectorizer_embed
    ( v.config operator(pg_catalog.->) 'embedding'
    , input_text
    , input_type
    )
    from ai.vectorizer v
    where v.id operator(pg_catalog.=) vectorizer_id
    ;
$func$ language sql stable security invoker
set search_path to pg_catalog, pg_temp
;

-- vectorizer_embed
create or replace function ai.vectorizer_embed
( name pg_catalog.text
, input_text pg_catalog.text
, input_type pg_catalog.text default null
) returns @extschema:vector@.vector
as $func$
    select ai.vectorizer_embed(v.id, input_text, input_type)
    from ai.vectorizer v
    where v.name operator(pg_catalog.=) vectorizer_embed.name
    ;
$func$ language sql stable security invoker
set search_path to pg_catalog, pg_temp;