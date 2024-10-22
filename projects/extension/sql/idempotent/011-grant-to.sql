-------------------------------------------------------------------------------
-- grant_to
create or replace function ai.grant_to(variadic grantees name[]) returns name[]
as $func$
    select coalesce(pg_catalog.array_agg(cast(x as name)), array[]::name[])
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
create or replace function ai.grant_to() returns name[]
as $func$
    select ai.grant_to(variadic array[]::name[])
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp
;
