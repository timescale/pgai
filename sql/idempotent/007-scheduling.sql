
-------------------------------------------------------------------------------
-- scheduling_none
create or replace function ai.scheduling_none() returns jsonb
as $func$
    select pg_catalog.jsonb_build_object('implementation', 'none')
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- scheduling_pg_cron
create or replace function ai.scheduling_pg_cron
( schedule text default '*/10 * * * *'
) returns jsonb
as $func$
    select pg_catalog.jsonb_build_object
    ( 'implementation', 'pg_cron'
    , 'schedule', schedule
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- scheduling_timescaledb
create or replace function ai.scheduling_timescaledb
( schedule_interval interval default interval '10m'
, initial_start timestamptz default null
, fixed_schedule bool default null
, timezone text default null
) returns jsonb
as $func$
    select json_object
    ( 'implementation': 'timescaledb'
    , 'schedule_interval': schedule_interval
    , 'initial_start': initial_start
    , 'fixed_schedule': fixed_schedule
    , 'timezone': timezone
    absent on null
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;
