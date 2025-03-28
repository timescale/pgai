do $block$
declare
    _vectorizer_is_in_extension boolean;
    _rec record;
    _sql text;
    _db_owner_name text;
    _acl_is_default boolean;
    _major_version integer;
    _maintain text;
begin
    select split_part(current_setting('server_version'), '.', 1)::INT into _major_version   ;
    if _major_version < 17 then
        _maintain := '';
    else
        _maintain := ',MAINTAIN';
    end if;

    --the vectorizer table is in the very first migration that used to be run as part of the extension install
    --so we can check if the vectorizer machinery is in the extension by checking if the vectorizer table exists
    select
        count(*) > 0 into _vectorizer_is_in_extension
    from pg_catalog.pg_depend d
    inner join pg_catalog.pg_class k on (d.objid = k.oid)
    inner join pg_catalog.pg_namespace n on (k.relnamespace = n.oid)
    inner join pg_catalog.pg_extension x on (d.refobjid = x.oid)
    where d.classid = 'pg_catalog.pg_class'::regclass::oid
    and d.refclassid = 'pg_catalog.pg_extension'::regclass::oid
    and d.deptype = 'e'
    and x.extname = 'ai'
    and n.nspname = 'ai'
    and k.relname = 'vectorizer';
    
    if not _vectorizer_is_in_extension then
        --the vectorizer machinery is not in the extension, so we can skip the divest process
        return;
    end if;
    
    drop function if exists ai._vectorizer_create_dependencies(integer);
    drop function if exists ai._vectorizer_handle_drops() cascade;
    
    select r.rolname into strict _db_owner_name
    from pg_catalog.pg_database d
    join pg_catalog.pg_authid r on d.datdba = r.oid
    where d.datname = current_database();

-------------------------------------------------------------------------------
-- schema, tables, views, sequences

    execute format('alter schema ai owner to %I;', _db_owner_name);
    
    execute format('create table ai.migration_app
    ( "name" text not null primary key
    , applied_at_version text not null
    , applied_at timestamptz not null default pg_catalog.clock_timestamp()
    , body text not null
    )');
    
    execute format('alter table ai.migration_app owner to %I', _db_owner_name);
    execute format('alter extension ai drop table ai.migration_app');

    insert into ai.migration_app (name, applied_at_version, applied_at, body)
    select "name", 'unpackaged', now(), body
    from ai.migration
    where name in (
        '001-vectorizer.sql'
        , '003-vec-storage.sql'
        , '005-vectorizer-queue-pending.sql'
        , '006-drop-vectorizer.sql'
        --, '009-drop-truncate-from-vectorizer-config.sql' --not included on purpose since it's not the same
        , '012-add-vectorizer-disabled-column.sql'
        , '017-upgrade-source-pk.sql'
        , '018-drop-foreign-key-constraint.sql'
    );

    for _rec in
    (
        select
          n.nspname
        , k.relname
        , k.oid
        , k.relkind
        from pg_catalog.pg_depend d
        inner join pg_catalog.pg_class k on (d.objid = k.oid)
        inner join pg_catalog.pg_namespace n on (k.relnamespace = n.oid)
        inner join pg_catalog.pg_extension x on (d.refobjid = x.oid)
        where d.classid = 'pg_catalog.pg_class'::regclass::oid
        and d.refclassid = 'pg_catalog.pg_extension'::regclass::oid
        and d.deptype = 'e'
        and x.extname = 'ai'
        and (n.nspname, k.relname) in
        (
            values
              ('ai', 'vectorizer_id_seq')
            , ('ai', 'vectorizer')
            , ('ai', 'vectorizer_errors')
            , ('ai', 'vectorizer_status')
        )
    )
    loop
        raise warning $$dropping ('%', '%')$$, _rec.nspname, _rec.relname;
        select format
        ( $sql$alter extension ai drop %s %I.%I$sql$
        , case _rec.relkind
            when 'r' then 'table'
            when 'S' then 'sequence'
            when 'v' then 'view'
          end
        , _rec.nspname
        , _rec.relname
        ) into strict _sql
        ;
        raise notice '%', _sql;
        execute _sql;
        
        if _rec.relname != 'vectorizer_id_seq' THEN
            select format
            ( $sql$alter %s %I.%I owner to %I$sql$
            , case _rec.relkind
                when 'r' then 'table'
                when 'S' then 'sequence'
                when 'v' then 'view'
            end
            , _rec.nspname
            , _rec.relname
            , _db_owner_name
            ) into strict _sql
            ;
            raise notice '%', _sql;
            execute _sql;
        end if;
      
        --see if the default acl is set for the db owner and reset to null if so 
        if _rec.relkind in ('r', 'v') then
            select relacl = array[ 
               makeaclitem(
                to_regrole(_db_owner_name)::oid, 
                to_regrole(_db_owner_name)::oid, 
                'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER' || _maintain, 
                TRUE),
                makeaclitem(
                to_regrole('pg_database_owner')::oid, 
                to_regrole(_db_owner_name)::oid, 
                'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER' || _maintain, 
                TRUE)
            ] into _acl_is_default
            from pg_catalog.pg_class c
            where c.oid = _rec.oid;
            
            if _acl_is_default then
                execute format('update pg_catalog.pg_class set relacl = NULL where oid = %L', _rec.oid);
            end if;
        end if;
    end loop;
    
    --check the vectorizer_id_seq acl and reset to null if it is the default (do this after the loop so we can see acl after the tables are changed)
    select  c.relacl = 
       array[
           makeaclitem(to_regrole(_db_owner_name)::oid, to_regrole(_db_owner_name)::oid, 'SELECT, USAGE, UPDATE', TRUE),
           makeaclitem(to_regrole('pg_database_owner')::oid, to_regrole(_db_owner_name)::oid, 'SELECT, USAGE, UPDATE', TRUE)
        ] 
    into _acl_is_default
    from pg_catalog.pg_class c
    where c.oid = to_regclass('ai.vectorizer_id_seq');
    
    if _acl_is_default is not null and _acl_is_default then
        execute format('update pg_catalog.pg_class set relacl = NULL where oid = %L', to_regclass('ai.vectorizer_id_seq')::oid);
    end if;
    
    --vectorizer had a grant option for the db owner, but now the db owner is the table owner so clean up the acl by removing the grant option
    select c.relacl @> 
           makeaclitem(
            to_regrole(_db_owner_name)::oid, 
            to_regrole(_db_owner_name)::oid, 
            'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER' || _maintain, 
            TRUE) into _acl_is_default
    from pg_catalog.pg_class c
    where c.oid = to_regclass('ai.vectorizer');
    
    if _acl_is_default is not null and _acl_is_default then
        execute format('revoke grant option for all on ai.vectorizer from %I', _db_owner_name);
    end if;
    
    --remove pg_database_owner grant on vectorizer entirely if it's the default grant
    select c.relacl @> 
           makeaclitem(
            to_regrole('pg_database_owner')::oid, 
            to_regrole(_db_owner_name)::oid, 
            'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER' || _maintain, 
            TRUE) into _acl_is_default
    from pg_catalog.pg_class c
    where c.oid = to_regclass('ai.vectorizer');
    
    if _acl_is_default is not null and _acl_is_default then
        execute format('revoke all on ai.vectorizer from pg_database_owner');
    end if;

-------------------------------------------------------------------------------
-- triggers

--nothing to do?

-------------------------------------------------------------------------------
-- event triggers

--no event triggers left

-------------------------------------------------------------------------------
-- functions, procedures
    for _rec in
    (
        select *
        from
        (
            select format
            ( $sql$%s %I.%I(%s)$sql$
            , case when p.prokind = 'f' then 'function' else 'procedure' end
            , n.nspname
            , p.proname
            , pg_catalog.pg_get_function_identity_arguments(p.oid)
            ) as spec
            , p.oid
            from pg_catalog.pg_depend d
            inner join pg_catalog.pg_proc p on (d.objid = p.oid)
            inner join pg_catalog.pg_namespace n on (p.pronamespace = n.oid)
            inner join pg_catalog.pg_extension x on (d.refobjid = x.oid)
            where d.classid = 'pg_catalog.pg_proc'::regclass::oid
            and d.refclassid = 'pg_catalog.pg_extension'::regclass::oid
            and d.deptype = 'e'
            and x.extname = 'ai'
        ) x
        where x.spec in
        ( 
         'function ai.chunking_character_text_splitter(chunk_column name, chunk_size integer, chunk_overlap integer, separator text, is_separator_regex boolean)'
        , 'function ai.chunking_recursive_character_text_splitter(chunk_column name, chunk_size integer, chunk_overlap integer, separators text[], is_separator_regex boolean)'
        , 'function ai._validate_chunking(config jsonb, source_schema name, source_table name)'
        , 'function ai.formatting_python_template(template text)'
        , 'function ai._validate_formatting_python_template(config jsonb, source_schema name, source_table name)'
        , 'function ai._validate_formatting(config jsonb, source_schema name, source_table name)'
        , 'function ai.scheduling_none()'
        , 'function ai.scheduling_default()'
        , 'function ai.scheduling_timescaledb(schedule_interval interval, initial_start timestamp with time zone, fixed_schedule boolean, timezone text)'
        , 'function ai._resolve_scheduling_default()'
        , 'function ai._validate_scheduling(config jsonb)'
        , 'function ai.embedding_openai(model text, dimensions integer, chat_user text, api_key_name text, base_url text)'
        , 'function ai.embedding_ollama(model text, dimensions integer, base_url text, options jsonb, keep_alive text)'
        , 'function ai.embedding_voyageai(model text, dimensions integer, input_type text, api_key_name text)'
        , 'function ai.embedding_litellm(model text, dimensions integer, api_key_name text, extra_options jsonb)'
        , 'function ai._validate_embedding(config jsonb)'
        , 'function ai.indexing_none()'
        , 'function ai.indexing_default()'
        , 'function ai.indexing_diskann(min_rows integer, storage_layout text, num_neighbors integer, search_list_size integer, max_alpha double precision, num_dimensions integer, num_bits_per_dimension integer, create_when_queue_empty boolean)'
        , 'function ai._resolve_indexing_default()'
        , 'function ai._validate_indexing_diskann(config jsonb)'
        , 'function ai.indexing_hnsw(min_rows integer, opclass text, m integer, ef_construction integer, create_when_queue_empty boolean)'
        , 'function ai._validate_indexing_hnsw(config jsonb)'
        , 'function ai._validate_indexing(config jsonb)'
        , 'function ai.processing_default(batch_size integer, concurrency integer)'
        , 'function ai._validate_processing(config jsonb)'
        , 'function ai.grant_to(VARIADIC grantees name[])'
        , 'function ai.grant_to()'
        , 'function ai._vectorizer_source_pk(source_table regclass)'
        , 'function ai._vectorizer_grant_to_source(source_schema name, source_table name, grant_to name[])'
        , 'function ai._vectorizer_grant_to_vectorizer(grant_to name[])'
        , 'function ai._vectorizer_create_target_table(source_pk jsonb, target_schema name, target_table name, dimensions integer, grant_to name[])'
        , 'function ai._vectorizer_create_view(view_schema name, view_name name, source_schema name, source_table name, source_pk jsonb, target_schema name, target_table name, grant_to name[])'
        , 'function ai._vectorizer_create_queue_table(queue_schema name, queue_table name, source_pk jsonb, grant_to name[])'
        , 'function ai._vectorizer_build_trigger_definition(queue_schema name, queue_table name, target_schema name, target_table name, source_pk jsonb)'
        , 'function ai._vectorizer_create_source_trigger(trigger_name name, queue_schema name, queue_table name, source_schema name, source_table name, target_schema name, target_table name, source_pk jsonb)'
        , 'function ai._vectorizer_create_source_trigger(trigger_name name, queue_schema name, queue_table name, source_schema name, source_table name, source_pk jsonb)'
        , 'function ai._vectorizer_create_target_table(source_schema name, source_table name, source_pk jsonb, target_schema name, target_table name, dimensions integer, grant_to name[])'
        , 'function ai.drop_vectorizer(vectorizer_id integer)'
        , 'function ai.vectorizer_queue_pending(vectorizer_id integer)'
        , 'function ai._vectorizer_vector_index_exists(target_schema name, target_table name, indexing jsonb)'
        , 'function ai._vectorizer_should_create_vector_index(vectorizer ai.vectorizer)'
        , 'function ai._vectorizer_create_vector_index(target_schema name, target_table name, indexing jsonb)'
        , 'procedure ai._vectorizer_job(IN job_id integer, IN config jsonb)'
        , 'function ai._vectorizer_schedule_job(vectorizer_id integer, scheduling jsonb)'
        , 'function ai.create_vectorizer(source regclass, destination name, embedding jsonb, chunking jsonb, indexing jsonb, formatting jsonb, scheduling jsonb, processing jsonb, target_schema name, target_table name, view_schema name, view_name name, queue_schema name, queue_table name, grant_to name[], enqueue_existing boolean)'
        , 'function ai.disable_vectorizer_schedule(vectorizer_id integer)'
        , 'function ai.enable_vectorizer_schedule(vectorizer_id integer)'
        , 'function ai.drop_vectorizer(vectorizer_id integer, drop_all boolean)'
        , 'function ai.vectorizer_queue_pending(vectorizer_id integer, exact_count boolean)'
        , 'function ai.vectorizer_embed(embedding_config jsonb, input_text text, input_type text)'
        , 'function ai.vectorizer_embed(vectorizer_id integer, input_text text, input_type text)'
        )
    )
    loop
        select format
        ( $sql$alter extension ai drop %s$sql$
        , _rec.spec
        ) into strict _sql
        ;
        raise notice '%', _sql;
        execute _sql;
        
        select format
        ( $sql$alter %s owner to %I$sql$
        , _rec.spec
        , _db_owner_name
        ) into strict _sql
        ;
        raise notice '%', _sql;
        execute _sql;
        
        --see if the default acl is set for the db owner and reset to null if so 
        select proacl = array[ 
           makeaclitem(
            to_regrole(_db_owner_name)::oid, 
            to_regrole(_db_owner_name)::oid, 
            'EXECUTE', 
            TRUE),
            makeaclitem(
            to_regrole('pg_database_owner')::oid, 
            to_regrole(_db_owner_name)::oid, 
            'EXECUTE', 
            TRUE)
        ] into _acl_is_default
        from pg_catalog.pg_proc p
        where p.oid = _rec.oid;
        
        if _acl_is_default then
            execute format('update pg_catalog.pg_proc set proacl = NULL where oid = %L', _rec.oid);
        end if;
    end loop;
end;
$block$;
