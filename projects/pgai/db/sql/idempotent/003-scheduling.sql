
-------------------------------------------------------------------------------
-- scheduling_none
create or replace function ai.scheduling_none() returns pg_catalog.jsonb
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
create or replace function ai.scheduling_default() returns pg_catalog.jsonb
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
( schedule_interval pg_catalog.interval default interval '5m'
, initial_start pg_catalog.timestamptz default null
, fixed_schedule pg_catalog.bool default null
, timezone pg_catalog.text default null
) returns pg_catalog.jsonb
as $func$
    select json_strip_nulls(json_build_object
    ( 'implementation', 'timescaledb'
    , 'config_type', 'scheduling'
    , 'schedule_interval', schedule_interval
    , 'initial_start', initial_start
    , 'fixed_schedule', fixed_schedule
    , 'timezone', timezone
    ))
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _resolve_scheduling_default
create or replace function ai._resolve_scheduling_default() returns pg_catalog.jsonb
as $func$
declare
    _setting pg_catalog.text;
begin
    select pg_catalog.current_setting('ai.scheduling_default', true) into _setting;
    case _setting
        when 'scheduling_timescaledb' then
            return ai.scheduling_timescaledb();
        else
            return ai.scheduling_none();
    end case;
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _validate_scheduling
create or replace function ai._validate_scheduling(config pg_catalog.jsonb) returns void
as $func$
declare
    _config_type pg_catalog.text;
    _implementation pg_catalog.text;
begin
    if pg_catalog.jsonb_typeof(config) operator(pg_catalog.!=) 'object' then
        raise exception 'scheduling config is not a jsonb object';
    end if;

    _config_type = config operator(pg_catalog.->>) 'config_type';
    if _config_type is null or _config_type operator(pg_catalog.!=) 'scheduling' then
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
