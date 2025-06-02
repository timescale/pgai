
-------------------------------------------------------------------------------
-- _vectorizer_source_pk
create or replace function ai._vectorizer_source_pk(source_table pg_catalog.regclass) returns pg_catalog.jsonb as
$func$
    select pg_catalog.jsonb_agg(x)
    from
    (
        select e.attnum, e.pknum, a.attname, pg_catalog.format_type(y.oid, a.atttypmod) as typname
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
-- _vectorizer_create_destination_table
create or replace function ai._vectorizer_create_destination_table
(   source_schema pg_catalog.name
    , source_table pg_catalog.name
    , source_pk pg_catalog.jsonb
    , dimensions pg_catalog.int4
    , destination jsonb
    , grant_to pg_catalog.name[]
) returns void as
$func$
declare
    target_schema pg_catalog.name;
    target_table pg_catalog.name;
    view_schema pg_catalog.name;
    view_name pg_catalog.name;
begin

    target_schema = destination operator(pg_catalog.->>) 'target_schema';
    target_table = destination operator(pg_catalog.->>) 'target_table';
    view_schema = destination operator(pg_catalog.->>) 'view_schema';
    view_name = destination operator(pg_catalog.->>) 'view_name';

    -- create the target table
    perform ai._vectorizer_create_target_table
    ( source_pk
    , target_schema
    , target_table
    , dimensions
    , grant_to
    );

    perform ai._vectorizer_create_view
    ( view_schema
    , view_name
    , source_schema
    , source_table
    , source_pk
    , target_schema
    , target_table
    , grant_to
    );
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

------------------------------------------------------------------------------- 
-- _vectorizer_create_destination_column
create or replace function ai._vectorizer_create_destination_column
(   source_schema pg_catalog.name
    , source_table pg_catalog.name
    , dimensions pg_catalog.int4
    , destination jsonb
) returns void as
$func$
declare
    embedding_column pg_catalog.name;
begin
    embedding_column = destination operator(pg_catalog.->>) 'embedding_column';
    perform ai._vectorizer_add_embedding_column
    ( source_schema
    , source_table
    , dimensions
    , embedding_column
    );
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _vectorizer_add_embedding_column
create or replace function ai._vectorizer_add_embedding_column
( source_schema pg_catalog.name
, source_table pg_catalog.name
, dimensions pg_catalog.int4
, embedding_column pg_catalog.name
) returns void as
$func$
declare
    _sql pg_catalog.text;
    _column_exists pg_catalog.bool;
begin
    -- Check if embedding column already exists
    select exists(
        select 1 
        from pg_catalog.pg_attribute a
        join pg_catalog.pg_class c on a.attrelid = c.oid
        join pg_catalog.pg_namespace n on c.relnamespace = n.oid
        where n.nspname = source_schema
        and c.relname = source_table
        and a.attname = embedding_column
        and not a.attisdropped
    ) into _column_exists;

    if _column_exists then
        raise notice 'embedding column %I already exists in %I.%I skipping creation', embedding_column, source_schema, source_table;
        return;
    else
        -- Add embedding column to source table
        select pg_catalog.format(
            $sql$
            alter table %I.%I 
            add column %I @extschema:vector@.vector(%L) default null
            $sql$,
            source_schema, source_table, embedding_column, dimensions
        ) into strict _sql;

        execute _sql;

        select pg_catalog.format(
            $sql$alter table %I.%I alter column %I set storage main$sql$,
            source_schema, source_table, embedding_column
        ) into strict _sql;

        execute _sql;
    end if;
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp;
-------------------------------------------------------------------------------
-- _vectorizer_create_target_table
create or replace function ai._vectorizer_create_target_table
( source_pk pg_catalog.jsonb
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
    , embedding @extschema:vector@.vector(%L) not null
    , unique (%s, chunk_seq)
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
    ) into strict _sql
    ;
    execute _sql;

    select pg_catalog.format
       ( $sql$alter table %I.%I alter column embedding set storage main$sql$
       , target_schema
       , target_table
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
    ( $sql$
      create table %I.%I
      ( %s
      , queued_at pg_catalog.timestamptz not null default now()
      , loading_retries pg_catalog.int4 not null default 0
      , loading_retry_after pg_catalog.timestamptz
      )
      $sql$
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
-- _vectorizer_create_queue_failed_table
create or replace function ai._vectorizer_create_queue_failed_table
( queue_schema pg_catalog.name
, queue_failed_table pg_catalog.name
, source_pk pg_catalog.jsonb
, grant_to pg_catalog.name[]
) returns void as
$func$
declare
    _sql pg_catalog.text;
begin
    -- create the table
    select pg_catalog.format
    ( $sql$
      create table %I.%I
      ( %s
      , created_at pg_catalog.timestamptz not null default now()
      , failure_step pg_catalog.text not null default ''
      )
      $sql$
    , queue_schema, queue_failed_table
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
    , queue_schema, queue_failed_table
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
        , queue_failed_table
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
-- _build_vectorizer_trigger_definition
create or replace function ai._vectorizer_build_trigger_definition
( queue_schema pg_catalog.name
, queue_table pg_catalog.name
, target_schema pg_catalog.name
, target_table pg_catalog.name
, source_schema pg_catalog.name
, source_table pg_catalog.name
, source_pk pg_catalog.jsonb
) returns pg_catalog.text as
$func$
declare
    _pk_change_check pg_catalog.text;
    _delete_statement pg_catalog.text;
    _pk_columns pg_catalog.text;
    _pk_values pg_catalog.text;
    _func_def pg_catalog.text;
    _relevant_columns_check pg_catalog.text;
    _truncate_statement pg_catalog.text;
begin
    -- Pre-calculate all the parts we need
    select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.attnum)
    into strict _pk_columns
    from pg_catalog.jsonb_to_recordset(source_pk) x(attnum int, attname name);

    select pg_catalog.string_agg(pg_catalog.format('new.%I', x.attname), ', ' order by x.attnum)
    into strict _pk_values
    from pg_catalog.jsonb_to_recordset(source_pk) x(attnum int, attname name);

    if target_schema is not null and target_table is not null then
        -- Create delete statement for deleted rows
        _delete_statement := format('delete from %I.%I where %s', target_schema, target_table,
            (select string_agg(format('%I = old.%I', attname, attname), ' and ')
            from pg_catalog.jsonb_to_recordset(source_pk) x(attnum int, attname name)));

        -- Create the primary key change check expression
        select string_agg(
            format('old.%I IS DISTINCT FROM new.%I', attname, attname),
            ' OR '
        )
        into strict _pk_change_check
        from pg_catalog.jsonb_to_recordset(source_pk) x(attnum int, attname name);

        _truncate_statement := format('truncate table %I.%I; truncate table %I.%I',
                                target_schema, target_table, queue_schema, queue_table);
    end if;

    _relevant_columns_check := 
        pg_catalog.format('EXISTS (
            SELECT 1 FROM pg_catalog.jsonb_each(to_jsonb(old)) AS o(key, value)
            JOIN pg_catalog.jsonb_each(to_jsonb(new)) AS n(key, value) 
            ON o.key = n.key
            WHERE o.value IS DISTINCT FROM n.value
            AND o.key != ALL(
                SELECT config operator(pg_catalog.->) ''destination'' operator(pg_catalog.->>) ''embedding_column''
                FROM ai.vectorizer 
                WHERE source_table = %L AND source_schema = %L
                AND config operator(pg_catalog.->) ''destination'' operator(pg_catalog.->>) ''implementation'' operator(pg_catalog.=) ''column''
            )
        )', source_table, source_schema);

    if target_schema is not null and target_table is not null then
        _func_def := $def$
        begin
            if (TG_LEVEL = 'ROW') then
                if (TG_OP = 'DELETE') then
                    $DELETE_STATEMENT$;
                elsif (TG_OP = 'UPDATE') then
                    -- Check if the primary key has changed and queue the update
                    if $PK_CHANGE_CHECK$ then
                        $DELETE_STATEMENT$;
                        insert into $QUEUE_SCHEMA$.$QUEUE_TABLE$ ($PK_COLUMNS$)
                            values ($PK_VALUES$);
                    -- check if a relevant column has changed and queue the update
                    elsif $RELEVANT_COLUMNS_CHECK$ then
                        insert into $QUEUE_SCHEMA$.$QUEUE_TABLE$ ($PK_COLUMNS$)
                        values ($PK_VALUES$);
                    end if;

                    return new;
                else
                    insert into $QUEUE_SCHEMA$.$QUEUE_TABLE$ ($PK_COLUMNS$)
                    values ($PK_VALUES$);
                    return new;
                end if;

            elsif (TG_LEVEL = 'STATEMENT') then
                if (TG_OP = 'TRUNCATE') then
                    $TRUNCATE_STATEMENT$;
                end if;
                return null;
            end if;

            return null;
        end;
        $def$;

        -- Replace placeholders
        _func_def := replace(_func_def, '$DELETE_STATEMENT$', _delete_statement);
        _func_def := replace(_func_def, '$PK_CHANGE_CHECK$', _pk_change_check);
        _func_def := replace(_func_def, '$QUEUE_SCHEMA$', quote_ident(queue_schema));
        _func_def := replace(_func_def, '$QUEUE_TABLE$', quote_ident(queue_table));
        _func_def := replace(_func_def, '$PK_COLUMNS$', _pk_columns);
        _func_def := replace(_func_def, '$PK_VALUES$', _pk_values);
        _func_def := replace(_func_def, '$TARGET_SCHEMA$', quote_ident(target_schema));
        _func_def := replace(_func_def, '$TARGET_TABLE$', quote_ident(target_table));
        _func_def := replace(_func_def, '$RELEVANT_COLUMNS_CHECK$', _relevant_columns_check);
        _func_def := replace(_func_def, '$TRUNCATE_STATEMENT$', _truncate_statement);
    
    else
        _func_def := $def$
        begin
            if (TG_LEVEL = 'ROW') then
                if (TG_OP = 'UPDATE') then
                    if $RELEVANT_COLUMNS_CHECK$ then
                        insert into $QUEUE_SCHEMA$.$QUEUE_TABLE$ ($PK_COLUMNS$)
                        values ($PK_VALUES$);
                    end if;
                elseif (TG_OP = 'INSERT') then
                    insert into $QUEUE_SCHEMA$.$QUEUE_TABLE$ ($PK_COLUMNS$)
                    values ($PK_VALUES$);
                end if;
            end if;
            return null;
        end;
        $def$;
        _func_def := replace(_func_def, '$RELEVANT_COLUMNS_CHECK$', _relevant_columns_check);
        _func_def := replace(_func_def, '$QUEUE_SCHEMA$', quote_ident(queue_schema));
        _func_def := replace(_func_def, '$QUEUE_TABLE$', quote_ident(queue_table));
        _func_def := replace(_func_def, '$PK_COLUMNS$', _pk_columns);
        _func_def := replace(_func_def, '$PK_VALUES$', _pk_values);
    end if;
    return _func_def;
end;
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- _vectorizer_create_source_trigger
create or replace function ai._vectorizer_create_source_trigger
( trigger_name pg_catalog.name     -- Name for the trigger
, queue_schema pg_catalog.name     -- Schema containing the queue table
, queue_table pg_catalog.name      -- Table that will store queued items
, source_schema pg_catalog.name    -- Schema containing the watched table
, source_table pg_catalog.name     -- Table being watched for changes
, target_schema pg_catalog.name    -- Schema containing the target table for deletions
, target_table pg_catalog.name     -- Table where corresponding rows should be deleted
, source_pk pg_catalog.jsonb       -- JSON describing primary key columns to track
) returns void as
$func$
declare
    _sql pg_catalog.text;
begin
    
    execute format
    ( $sql$
    create function %I.%I() returns trigger 
    as $trigger_def$ 
    %s
    $trigger_def$ language plpgsql volatile parallel safe security definer 
    set search_path to pg_catalog, pg_temp
    $sql$
    , queue_schema
    , trigger_name
    , ai._vectorizer_build_trigger_definition(queue_schema,
                                              queue_table,
                                              target_schema,
                                              target_table,
                                              source_schema,
                                              source_table,
                                              source_pk)
    );

    -- Revoke public permissions
    _sql := pg_catalog.format(
        'revoke all on function %I.%I() from public',
        queue_schema, trigger_name
    );
    execute _sql;

    -- Create the row-level trigger
    select pg_catalog.format(
        $sql$
        create trigger %I
        after insert or update or delete
        on %I.%I
        for each row execute function %I.%I()
        $sql$,
        trigger_name,
        source_schema, source_table,
        queue_schema, trigger_name
    ) into strict _sql
    ;
    execute _sql;
    
    -- Create the statement-level trigger for TRUNCATE
    -- Note: Using the same trigger function but with a different event and level
    select pg_catalog.format(
        $sql$
        create trigger %I_truncate
        after truncate
        on %I.%I
        for each statement execute function %I.%I()
        $sql$,
        trigger_name,
        source_schema, source_table,
        queue_schema, trigger_name
    ) into strict _sql
    ;
    execute _sql;
end;
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-- This code block recreates all trigger functions for vectorizers to make sure
-- they have the most recent code for the function.
do $upgrade_block$
declare
    _vec record;
    _target_schema pg_catalog.name;
    _target_table pg_catalog.name;
    _destination_type pg_catalog.text;
begin
    -- Find all vectorizers
    for _vec in (
        select 
            v.id,
            v.source_schema,
            v.source_table,
            v.source_pk,
            v.trigger_name,
            v.queue_schema,
            v.queue_table,
            v.config
        from ai.vectorizer v
    )
    loop
        raise notice 'Recreating trigger function for vectorizer ID %s', _vec.id;
        
        _destination_type := _vec.config->'destination'->>'implementation';
        if _destination_type = 'table' then
            _target_schema := _vec.config->'destination'->>'target_schema';
            _target_table := _vec.config->'destination'->>'target_table';
        else -- destination column works with no target table in the trigger def
            _target_schema := null;
            _target_table := null;
        end if;

        execute format
        (
        --weird indent is intentional to make the sql functions look the same as during a fresh install
        --otherwise the snapshots will not match during upgrade testing.
            $sql$
    create or replace function %I.%I() returns trigger 
    as $trigger_def$ 
    %s 
    $trigger_def$ language plpgsql volatile parallel safe security definer 
    set search_path to pg_catalog, pg_temp
    $sql$
            , _vec.queue_schema, _vec.trigger_name,
            ai._vectorizer_build_trigger_definition(_vec.queue_schema,
                                                    _vec.queue_table,
                                                    _target_schema,
                                                    _target_table,
                                                    _vec.source_schema,
                                                    _vec.source_table,
                                                    _vec.source_pk)
        );
    end loop;
end;
$upgrade_block$;

-------------------------------------------------------------------------------
-- _vectorizer_vector_index_exists
create or replace function ai._vectorizer_vector_index_exists
( target_schema pg_catalog.name
, target_table pg_catalog.name
, indexing pg_catalog.jsonb
, column_name pg_catalog.name default 'embedding'
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
        and a.attname operator(pg_catalog.=) column_name
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
    _schema_name pg_catalog.name;
    _table_name pg_catalog.name;
    _column_name pg_catalog.name;
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

    _schema_name = coalesce(vectorizer.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'target_schema', vectorizer.source_schema);
    _table_name = coalesce(vectorizer.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'target_table', vectorizer.source_table);
    _column_name = coalesce(vectorizer.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'embedding_column', 'embedding');
    -- see if the index already exists. if so, exit
    if ai._vectorizer_vector_index_exists(_schema_name, _table_name, _indexing, _column_name) then
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
            raise notice 'queue for %.% is not empty. skipping vector index creation', _schema_name, _table_name;
            return false;
        end if;
    end if;

    -- if min_rows has a value
    _min_rows = coalesce(pg_catalog.jsonb_extract_path_text(_indexing, 'min_rows')::pg_catalog.int8, 0);
    if _min_rows > 0 then
        -- count the rows in the target table
        select pg_catalog.format
        ( $sql$select pg_catalog.count(*) from (select 1 from %I.%I limit %L) x$sql$
        , _schema_name
        , _table_name
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
, column_name pg_catalog.name default 'embedding'
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
    if ai._vectorizer_vector_index_exists(target_schema, target_table, indexing, column_name) then
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
            ( $sql$create index on %I.%I using diskann (%I)%s$sql$
            , target_schema, target_table
            , column_name
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
            ( $sql$create index on %I.%I using hnsw (%I %I.%s)%s$sql$
            , target_schema, target_table
            , column_name
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
    _ai_extension_exists pg_catalog.bool;
begin
    select pg_catalog.jsonb_extract_path_text(scheduling, 'implementation')
    into strict _implementation
    ;
    case
        when _implementation operator(pg_catalog.=) 'timescaledb' then
            select pg_catalog.count(*) > 0
            into strict _ai_extension_exists
            from pg_catalog.pg_extension x
            where x.extname operator(pg_catalog.=) 'ai';
            
            if not _ai_extension_exists then
                raise exception 'ai extension not found but it is needed for timescaledb scheduling.';
            end if;
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
    _should_create_vector_index pg_catalog.bool;
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

    _should_create_vector_index = ai._vectorizer_should_create_vector_index(_vec);

    -- if the conditions are right, create the vectorizer index
    if _should_create_vector_index and _vec.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'implementation' operator(pg_catalog.=) 'table' then
        commit;
        set local search_path = pg_catalog, pg_temp;
        perform ai._vectorizer_create_vector_index
        (_vec.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'target_schema'
        , _vec.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'target_table'
        , pg_catalog.jsonb_extract_path(_vec.config, 'indexing')
        );
    elsif _should_create_vector_index and _vec.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'implementation' operator(pg_catalog.=) 'column' then
        commit;
        set local search_path = pg_catalog, pg_temp;
        perform ai._vectorizer_create_vector_index
        (_vec.source_schema
        , _vec.source_table
        , pg_catalog.jsonb_extract_path(_vec.config, 'indexing')
        , _vec.config operator(pg_catalog.->) 'destination' operator(pg_catalog.->>) 'embedding_column'
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
-- execute_vectorizer by vectorizer name
create or replace function ai.execute_vectorizer(vectorizer_name pg_catalog.text) returns void
as $func$
declare
    _vectorizer_id pg_catalog.int4;
begin
    select v.id into strict _vectorizer_id
    from ai.vectorizer v
    where v.name operator(pg_catalog.=) vectorizer_name;

    -- execute the vectorizer
    perform ai.execute_vectorizer(_vectorizer_id);
end
$func$
language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;