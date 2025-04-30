create extension if not exists timescaledb with schema public cascade;
create extension if not exists timescaledb_toolkit with schema public cascade;

create table if not exists postgres_air.events
(
    time timestamp not null,
    name text not null,
    params jsonb not null
);
SELECT public.create_hypertable('postgres_air.events', public.by_range('time'));

create materialized view postgres_air.events_daily
with (timescaledb.continuous) as
select
    name,
    public.time_bucket(INTERVAL '1 day', time) as bucket
from postgres_air.events
group by name, bucket;

CREATE TABLE postgres_air.hypertable_test (
  time timestamp with time zone,
  location varchar,
  time_received timestamp with time zone,
  params jsonb
);
CREATE FUNCTION public.hypertable_test_func(jsonb)
    RETURNS timestamptz
    LANGUAGE SQL
    IMMUTABLE AS
$func$SELECT ($1->>'started')::timestamptz$func$;
SELECT create_hypertable('postgres_air.hypertable_test', by_range('time'));
SELECT add_dimension('postgres_air.hypertable_test', by_hash('location', 2));
SELECT add_dimension('postgres_air.hypertable_test', by_range('time_received', INTERVAL '1 day'));
SELECT add_dimension('postgres_air.hypertable_test', by_range('params', INTERVAL '1 day', partition_func => 'public.hypertable_test_func'));

CREATE AGGREGATE postgres_air.unsafe_sum (float8)
(
    stype = float8,
    sfunc = float8pl,
    mstype = float8,
    msfunc = float8pl,
    minvfunc = float8mi,
    initcond = 10
);
