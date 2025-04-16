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
    begin
    raise 'This trigger function should be redefined in the idempotent code'; 
    end 
    $trigger_def$ language plpgsql volatile parallel safe security definer 
    set search_path to pg_catalog, pg_temp
    $sql$
            , _vec.queue_schema, _vec.trigger_name
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
