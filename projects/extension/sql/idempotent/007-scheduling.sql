
-------------------------------------------------------------------------------
-- scheduling_none
create or replace function ai.scheduling_none() returns jsonb
as $func$
    select pg_catalog.jsonb_build_object
    ( 'implementation', 'none'
    , 'config_type', 'scheduling'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- scheduling_default
create or replace function ai.scheduling_default() returns jsonb
as $func$
    select pg_catalog.jsonb_build_object
    ( 'implementation', 'default'
    , 'config_type', 'scheduling'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- scheduling_timescaledb
create or replace function ai.scheduling_timescaledb
( schedule_interval interval default interval '5m'
, initial_start timestamptz default null
, fixed_schedule bool default null
, timezone text default null
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'timescaledb'
    , 'config_type': 'scheduling'
    , 'schedule_interval': schedule_interval
    , 'initial_start': initial_start
    , 'fixed_schedule': fixed_schedule
    , 'timezone': timezone
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _resolve_scheduling_default
create or replace function ai._resolve_scheduling_default() returns jsonb
as $func$
declare
    _setting text;
begin
    select pg_catalog.current_setting('ai.scheduling_default', missing_ok=>true) into _setting;
    case _setting
        when 'scheduling_timescaledb' then
            return ai.scheduling_timescaledb();
        when 'scheduling_none' then
            return ai.scheduling_none();
    end case;
    return ai.scheduling_none();
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_scheduling
create or replace function ai._validate_scheduling(config jsonb) returns void
as $func$
declare
    _config_type text;
    _implementation text;
begin
    if pg_catalog.jsonb_typeof(config) != 'object' then
        raise exception 'scheduling config is not a jsonb object';
    end if;

    _config_type = config operator ( pg_catalog.->> ) 'config_type';
    if _config_type is null or _config_type != 'scheduling' then
        raise exception 'invalid config_type for scheduling config';
    end if;
    _implementation = config operator(pg_catalog.->>) 'implementation';
    case _implementation
        when 'none' then
            -- ok
        when 'timescaledb' then
            -- ok
        else
            if _implementation is null then
                raise exception 'scheduling implementation not specified';
            else
                raise exception 'unrecognized scheduling implementation: "%"', _implementation;
            end if;
    end case;
end
$func$ language plpgsql immutable security invoker
set search_path to pg_catalog, pg_temp
;
