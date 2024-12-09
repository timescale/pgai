-------------------------------------------------------------------------------
-- create_vectorizer
create or replace function ai.create_vectorizer
( source regclass
, destination name default null
, embedding jsonb default null
, chunking jsonb default null
, indexing jsonb default ai.indexing_default()
, formatting jsonb default ai.formatting_python_template()
, scheduling jsonb default ai.scheduling_default()
, processing jsonb default ai.processing_default()
, target_schema name default null
, target_table name default null
, view_schema name default null
, view_name name default null
, queue_schema name default null
, queue_table name default null
, grant_to name[] default ai.grant_to()
, enqueue_existing bool default true
) returns int
as $func$
declare
    _missing_roles name[];
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
    -- make sure all the roles listed in grant_to exist
    if grant_to is not null then
        select
          pg_catalog.array_agg(r) filter (where pg_catalog.to_regrole(r) is null) -- missing
        , pg_catalog.array_agg(r) filter (where pg_catalog.to_regrole(r) is not null) -- real roles
        into strict
          _missing_roles
        , grant_to
        from pg_catalog.unnest(grant_to) r
        ;
        if pg_catalog.array_length(_missing_roles, 1) > 0 then
            raise warning 'one or more grant_to roles do not exist: %', _missing_roles;
        end if;
    end if;
    
    if embedding is null then
        raise exception 'embedding configuration is required';
    end if;
    
    if chunking is null then
        raise exception 'chunking configuration is required';
    end if;

    -- get source table name and schema name
    select k.relname, n.nspname, pg_catalog.pg_has_role(pg_catalog.current_user(), k.relowner, 'MEMBER')
    into strict _source_table, _source_schema, _is_owner
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
    where k.oid operator(pg_catalog.=) source
    ;

    if not _is_owner then
        raise exception 'only the owner of the source table may create a vectorizer on it';
    end if;

    select (embedding operator(pg_catalog.->) 'dimensions')::int into _dimensions;
    if _dimensions is null then
        raise exception '_dimensions argument is required';
    end if;

    -- get the source table's primary key definition
    select ai._vectorizer_source_pk(source) into strict _source_pk;
    if _source_pk is null or pg_catalog.jsonb_array_length(_source_pk) = 0 then
        raise exception 'source table must have a primary key constraint';
    end if;

    _vectorizer_id = pg_catalog.nextval('ai.vectorizer_id_seq'::pg_catalog.regclass);
    target_schema = coalesce(target_schema, _source_schema);
    target_table = case
        when target_table is not null then target_table
        when destination is not null then pg_catalog.concat(destination, '_store')
        else pg_catalog.concat(_source_table, '_embedding_store')
    end;
    view_schema = coalesce(view_schema, _source_schema);
    view_name = case
        when view_name is not null then view_name
        when destination is not null then destination
        else pg_catalog.concat(_source_table, '_embedding')
    end;
    _trigger_name = pg_catalog.concat('_vectorizer_src_trg_', _vectorizer_id);
    queue_schema = coalesce(queue_schema, 'ai');
    queue_table = coalesce(queue_table, pg_catalog.concat('_vectorizer_q_', _vectorizer_id));

    -- make sure view name is available
    if pg_catalog.to_regclass(pg_catalog.format('%I.%I', view_schema, view_name)) is not null then
        raise exception 'an object named %.% already exists. specify an alternate destination explicitly', view_schema, view_name;
    end if;

    -- make sure target table name is available
    if pg_catalog.to_regclass(pg_catalog.format('%I.%I', target_schema, target_table)) is not null then
        raise exception 'an object named %.% already exists. specify an alternate destination or target_table explicitly', target_schema, target_table;
    end if;

    -- make sure queue table name is available
    if pg_catalog.to_regclass(pg_catalog.format('%I.%I', queue_schema, queue_table)) is not null then
        raise exception 'an object named %.% already exists. specify an alternate queue_table explicitly', queue_schema, queue_table;
    end if;

    -- validate the embedding config
    perform ai._validate_embedding(embedding);

    -- validate the chunking config
    perform ai._validate_chunking(chunking, _source_schema, _source_table);

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

    -- grant select to source table
    perform ai._vectorizer_grant_to_source
    ( _source_schema
    , _source_table
    , grant_to
    );

    -- create the target table
    perform ai._vectorizer_create_target_table
    ( _source_schema
    , _source_table
    , _source_pk
    , target_schema
    , target_table
    , _dimensions
    , grant_to
    );

    -- create queue table
    perform ai._vectorizer_create_queue_table
    ( queue_schema
    , queue_table
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
    , grant_to
    );

    -- schedule the async ext job
    select ai._vectorizer_schedule_job
    (_vectorizer_id
    , scheduling
    ) into _job_id
    ;
    if _job_id is not null then
        scheduling = pg_catalog.jsonb_insert(scheduling, array['job_id'], to_jsonb(_job_id));
    end if;

    insert into ai.vectorizer
    ( id
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
      ( 'version', '0.5.0'
      , 'embedding', embedding
      , 'chunking', chunking
      , 'indexing', indexing
      , 'formatting', formatting
      , 'scheduling', scheduling
      , 'processing', processing
      )
    );

    -- record dependencies in pg_depend
    perform ai._vectorizer_create_dependencies(_vectorizer_id);

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

