create extension if not exists timescaledb with schema postgres_air cascade;
create extension if not exists timescaledb_toolkit with schema postgres_air cascade;

create table if not exists postgres_air.events
(
    time timestamp not null,
    name text not null,
    params jsonb not null
);
SELECT postgres_air.create_hypertable('postgres_air.events', postgres_air.by_range('time'));

create materialized view postgres_air.events_daily
with (timescaledb.continuous) as
select
    name,
    postgres_air.time_bucket(INTERVAL '1 day', time) as bucket
from postgres_air.events
group by name, bucket;
