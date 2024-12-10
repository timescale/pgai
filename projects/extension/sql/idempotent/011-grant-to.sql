-------------------------------------------------------------------------------
-- grant_to
create or replace function ai.grant_to(variadic grantees pg_catalog.name[]) returns pg_catalog.name[]
as $func$
    select coalesce(pg_catalog.array_agg(cast(x as pg_catalog.name)), array[]::pg_catalog.name[])
    from (
        select pg_catalog.unnest(grantees) x
        union
        select trim(pg_catalog.string_to_table(pg_catalog.current_setting('ai.grant_to_default', true), ',')) x
    ) _;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- grant_to
create or replace function ai.grant_to() returns pg_catalog.name[]
as $func$
    select ai.grant_to(variadic array[]::pg_catalog.name[])
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;
