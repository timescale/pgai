
-------------------------------------------------------------------------------
-- indexing_none
create or replace function ai.indexing_none() returns jsonb
as $func$
    select jsonb_build_object
    ( 'implementation', 'none'
    , 'config_type', 'indexing'
    )
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
    , 'config_type': 'indexing'
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
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- indexing_hnsw
create or replace function ai.indexing_hnsw
( min_rows int default 100000
, opclass text default 'vector_cosine_ops'
, m int default null
, ef_construction int default null
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'hnsw'
    , 'config_type': 'indexing'
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
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_indexing
create or replace function ai._validate_indexing(config jsonb) returns void
as $func$
declare
    _config_type text;
    _implementation text;
begin
    if pg_catalog.jsonb_typeof(config) != 'object' then
        raise exception 'indexing config is not a jsonb object';
    end if;

    _config_type = config operator ( pg_catalog.->> ) 'config_type';
    if _config_type is null or _config_type != 'indexing' then
        raise exception 'invalid config_type for indexing config';
    end if;
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
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;

