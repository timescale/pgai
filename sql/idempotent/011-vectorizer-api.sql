

-------------------------------------------------------------------------------
-- execute_vectorizer
create or replace function ai.execute_vectorizer(vectorizer_id int) returns void
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.vectorizer
    ai.vectorizer.execute_async_ext_vectorizer(plpy, vectorizer_id)
$python$
language plpython3u volatile security invoker
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
    _trigger_name = pg_catalog.concat('_vectorizer_src_trg_', _vectorizer_id);
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

-------------------------------------------------------------------------------
-- disable_vectorizer_schedule
create or replace function ai.disable_vectorizer_schedule(vectorizer_id int) returns void
as $func$
declare
    _vec ai.vectorizer%rowtype;
    _schedule jsonb;
    _job_id bigint;
    _sql text;
begin
    select * into strict _vec
    from ai.vectorizer v
    where v.id operator(pg_catalog.=) vectorizer_id
    ;
    -- enable the scheduled job if exists
    _schedule = _vec.config operator(pg_catalog.->) 'scheduling';
    if _schedule is not null then
        case _schedule operator(pg_catalog.->>) 'implementation'
            when 'none' then -- ok
            when 'timescaledb' then
                _job_id = (_schedule operator(pg_catalog.->) 'job_id')::bigint;
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
            when 'pg_cron' then
                _job_id = (_schedule operator(pg_catalog.->) 'job_id')::bigint;
                select pg_catalog.format
                ( $$select cron.alter_job(jobid, active=>false) from cron.job where jobid = %L$$
                , _job_id
                ) into _sql
                from pg_catalog.pg_extension x
                where x.extname = 'pg_cron'
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

-------------------------------------------------------------------------------
-- enable_vectorizer_schedule
create or replace function ai.enable_vectorizer_schedule(vectorizer_id int) returns void
as $func$
declare
    _vec ai.vectorizer%rowtype;
    _schedule jsonb;
    _job_id bigint;
    _sql text;
begin
    select * into strict _vec
    from ai.vectorizer v
    where v.id operator(pg_catalog.=) vectorizer_id
    ;
    -- enable the scheduled job if exists
    _schedule = _vec.config operator(pg_catalog.->) 'scheduling';
    if _schedule is not null then
        case _schedule operator(pg_catalog.->>) 'implementation'
            when 'none' then -- ok
            when 'timescaledb' then
                _job_id = (_schedule operator(pg_catalog.->) 'job_id')::bigint;
                select pg_catalog.format
                ( $$select %I.alter_job(job_id, scheduled=>true) from timescaledb_information.jobs where job_id = %L$$
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
            when 'pg_cron' then
                _job_id = (_schedule operator(pg_catalog.->) 'job_id')::bigint;
                select pg_catalog.format
                ( $$select cron.alter_job(jobid, active=>true) from cron.job where jobid = %L$$
                , _job_id
                ) into _sql
                from pg_catalog.pg_extension x
                where x.extname = 'pg_cron'
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

-------------------------------------------------------------------------------
-- drop_vectorizer
create or replace function ai.drop_vectorizer(vectorizer_id int) returns void
as $func$
/* drop_vectorizer
This function does the following:
1. deletes the scheduled job if any
2. drops the trigger from the source table
3. drops the trigger function
4. drops the queue table
5. deletes the vectorizer row

It does NOT:
1. drop the target table containing the embeddings
2. drop the view joining the target and source
*/
declare
    _vec ai.vectorizer%rowtype;
    _schedule jsonb;
    _job_id bigint;
    _trigger pg_catalog.pg_trigger%rowtype;
    _sql text;
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
                _job_id = (_schedule operator(pg_catalog.->) 'job_id')::bigint;
                select pg_catalog.format
                ( $$select %I.delete_job(job_id) from timescaledb_information.jobs where job_id = %L$$
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
            when 'pg_cron' then
                _job_id = (_schedule operator(pg_catalog.->) 'job_id')::bigint;
                select pg_catalog.format
                ( $$select cron.unschedule(jobid) from cron.job where jobid = %L$$
                , _job_id
                ) into _sql
                from pg_catalog.pg_extension x
                where x.extname = 'pg_cron'
                ;
                if _sql is not null then
                    execute _sql;
                end if;
        end case;
    end if;

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

-------------------------------------------------------------------------------
-- vectorizer_queue_pending
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

-------------------------------------------------------------------------------
-- vectorizer_status
create or replace view ai.vectorizer_status as
select
  v.id
, pg_catalog.format('%I.%I', v.source_schema, v.source_table) as source_table
, pg_catalog.format('%I.%I', v.target_schema, v.target_table) as target_table
, pg_catalog.format('%I.%I', v.view_schema, v.view_name) as "view"
, case when v.queue_table is not null then
    ai.vectorizer_queue_pending(v.id)
  else 0
  end as pending_items
from ai.vectorizer v
;
