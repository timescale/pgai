do language plpgsql $block$
declare
    _vectorizer RECORD;
    _target_schema text;
    _target_table text;
    _view_schema text;
    _view_name text;
    _config jsonb;
begin
    -- Loop through all vectorizers
    for _vectorizer in select id, target_schema, target_table, view_schema, view_name, config from ai.vectorizer
    loop
        -- Extract the chunking config and chunk_column
        _target_schema := _vectorizer.target_schema;
        _target_table := _vectorizer.target_table;
        _view_schema := _vectorizer.view_schema;
        _view_name := _vectorizer.view_name;

        -- Create new config:
        -- Add destination config
        _config := _vectorizer.config operator(pg_catalog.||) jsonb_build_object(
            'destination', json_build_object(
                'implementation', 'table',
                'config_type', 'destination',
                'target_schema', _target_schema,
                'target_table', _target_table,
                'view_schema', _view_schema,
                'view_name', _view_name
        ));

        -- Update the vectorizer with new config
        update ai.vectorizer 
        set config = _config
        where id operator(pg_catalog.=) _vectorizer.id;
    end loop;
end;
$block$;

-- These will be recreated by the idempotent migrations in new form that work despite the dropped columns
drop view if exists ai.vectorizer_status; 
drop event trigger if exists _vectorizer_handle_drops;
drop function if exists ai._vectorizer_handle_drops;

alter table ai.vectorizer 
    drop column target_schema,
    drop column target_table,
    drop column view_schema,
    drop column view_name;


drop FUNCTION IF EXISTS ai._vectorizer_build_trigger_definition(name,name,name,name,jsonb);
drop FUNCTION IF EXISTS ai.create_vectorizer(regclass,name,jsonb,jsonb,jsonb,jsonb,jsonb,jsonb,name,name,name,name,name,name,name[],boolean);
drop function if exists ai._vectorizer_vector_index_exists(name,name,jsonb);
drop function if exists ai._vectorizer_create_vector_index(name,name,jsonb);