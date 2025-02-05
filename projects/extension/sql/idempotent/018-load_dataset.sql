create or replace procedure ai.load_dataset_multi_txn
( name text
, config_name text default null
, split text default null
, schema_name name default 'public'
, table_name name default null
, if_table_exists text default 'error'
, field_types jsonb default null
, batch_size int default 5000
, max_batches int default null
, commit_every_n_batches int default 1
, kwargs jsonb default '{}'
)
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.load_dataset
    import json
     
    # Convert kwargs from json string to dict
    kwargs_dict = {}
    if kwargs:
        kwargs_dict = json.loads(kwargs)
    
    # Convert field_types from json string to dict
    field_types_dict = None 
    if field_types:
        field_types_dict = json.loads(field_types)
    
    
    num_rows = ai.load_dataset.load_dataset(
        plpy,
        name=name,
        config_name=config_name,
        split=split,
        schema=schema_name,
        table_name=table_name,
        if_table_exists=if_table_exists,
        field_types=field_types_dict,
        batch_size=batch_size,
        max_batches=max_batches,
        commit_every_n_batches=commit_every_n_batches,
        **kwargs_dict
    )
$python$
language plpython3u security invoker;

create or replace function ai.load_dataset
( name text
, config_name text default null
, split text default null
, schema_name name default 'public'
, table_name name default null
, if_table_exists text default 'error'
, field_types jsonb default null
, batch_size int default 5000
, max_batches int default null
, kwargs jsonb default '{}'
) returns bigint
as $python$
    #ADD-PYTHON-LIB-DIR
    import ai.load_dataset
    import json
    
    # Convert kwargs from json string to dict
    kwargs_dict = {}
    if kwargs:
        kwargs_dict = json.loads(kwargs)
    
    # Convert field_types from json string to dict
    field_types_dict = None 
    if field_types:
        field_types_dict = json.loads(field_types)
    
    return ai.load_dataset.load_dataset(
        plpy,
        name=name,
        config_name=config_name,
        split=split,
        schema=schema_name,
        table_name=table_name,
        if_table_exists=if_table_exists,
        field_types=field_types_dict,
        batch_size=batch_size,
        max_batches=max_batches,
        commit_every_n_batches=None,
        **kwargs_dict
    )
$python$
language plpython3u volatile security invoker
set search_path to pg_catalog, pg_temp;