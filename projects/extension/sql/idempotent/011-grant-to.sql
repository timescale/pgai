-------------------------------------------------------------------------------
-- grant_to
create or replace function ai.grant_to(variadic grantees name[]) returns name[]
as $func$
    select pg_catalog.array_agg(cast(x as name))
    from (
        select pg_catalog.unnest(grantees) x
        union
        select pg_catalog.unnest(pg_catalog.string_to_array(pg_catalog.current_setting('ai.grant_to_default', true), ',')) x
    ) _;
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;
