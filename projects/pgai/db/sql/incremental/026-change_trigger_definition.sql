-------------------------------------------------------------------------------
-- _build_vectorizer_trigger_definition
create or replace function ai._vectorizer_build_trigger_definition
( queue_schema pg_catalog.name
, queue_table pg_catalog.name
, target_schema pg_catalog.name
, target_table pg_catalog.name
, source_pk pg_catalog.jsonb
) returns pg_catalog.text as
$func$
declare
    _pk_change_check pg_catalog.text;
    _delete_statement pg_catalog.text;
    _pk_columns pg_catalog.text;
    _pk_values pg_catalog.text;
    _func_def pg_catalog.text;
begin
    -- Pre-calculate all the parts we need
    select pg_catalog.string_agg(pg_catalog.format('%I', x.attname), ', ' order by x.attnum)
    into strict _pk_columns
    from pg_catalog.jsonb_to_recordset(source_pk) x(attnum int, attname name);

    select pg_catalog.string_agg(pg_catalog.format('new.%I', x.attname), ', ' order by x.attnum)
    into strict _pk_values
    from pg_catalog.jsonb_to_recordset(source_pk) x(attnum int, attname name);

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
    _func_def := $def$
    begin
        if (TG_LEVEL = 'ROW') then
            if (TG_OP = 'DELETE') then
                $DELETE_STATEMENT$;
            elsif (TG_OP = 'UPDATE') then
                if $PK_CHANGE_CHECK$ then
                    $DELETE_STATEMENT$;
                end if;
                
                insert into $QUEUE_SCHEMA$.$QUEUE_TABLE$ ($PK_COLUMNS$)
                values ($PK_VALUES$);
                return new;
            else
                insert into $QUEUE_SCHEMA$.$QUEUE_TABLE$ ($PK_COLUMNS$)
                values ($PK_VALUES$);
                return new;
            end if;

        elsif (TG_LEVEL = 'STATEMENT') then
            if (TG_OP = 'TRUNCATE') then
                execute format('truncate table %I.%I', '$TARGET_SCHEMA$', '$TARGET_TABLE$');
                execute format('truncate table %I.%I', '$QUEUE_SCHEMA$', '$QUEUE_TABLE$');
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

    return _func_def;
end;
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp;

-- This code block recreates all triggers for vectorizers to make sure
-- they have the most recent version of the trigger function
do $upgrade_block$
declare
    _vec record;
begin
    -- Find all vectorizers
    for _vec in (
        select 
            v.id,
            v.source_schema,
            v.source_table,
            v.source_pk,
            v.target_schema,
            v.target_table,
            v.trigger_name,
            v.queue_schema,
            v.queue_table,
            v.config
        from ai.vectorizer v
    )
    loop
        raise notice 'Recreating trigger function for vectorizer ID %s', _vec.id;

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
            ai._vectorizer_build_trigger_definition(_vec.queue_schema, _vec.queue_table, _vec.target_schema, _vec.target_table, _vec.source_pk)
        );

        execute format(
            'drop trigger if exists %I on %I.%I',
            _vec.trigger_name, _vec.source_schema, _vec.source_table
        );

        execute format(
            'drop trigger if exists %I on %I.%I',
            format('%s_truncate',_vec.trigger_name) , _vec.source_schema, _vec.source_table
        );

        execute format(
            'create trigger %I after insert or update or delete on %I.%I for each row execute function %I.%I()',
            _vec.trigger_name, _vec.source_schema, _vec.source_table, _vec.queue_schema, _vec.trigger_name
        );

        execute format(
            'create trigger %I after truncate on %I.%I for each statement execute function %I.%I()',
            format('%s_truncate',_vec.trigger_name) , _vec.source_schema, _vec.source_table, _vec.queue_schema, _vec.trigger_name
        );
        
        raise info 'Successfully recreated trigger for vectorizer ID %', _vec.id;
    end loop;
end;
$upgrade_block$;
