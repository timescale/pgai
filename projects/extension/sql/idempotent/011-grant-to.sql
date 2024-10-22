
-------------------------------------------------------------------------------
-- grant_to_timescale
create or replace function ai.grant_to_timescale(variadic grantees name[]) returns jsonb
as $func$
    select jsonb_build_object
    ( 'implementation', 'timescale'
    , 'config_type', 'grant_to'
    , 'grant_to', pg_catalog.jsonb_build_array('tsdbadmin') operator(pg_catalog.||) pg_catalog.to_jsonb(grantees)
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- grant_to_default
create or replace function ai.grant_to_default() returns jsonb
as $func$
    select jsonb_build_object
    ( 'implementation', 'default'
    , 'config_type', 'grant_to'
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- grant_to
create or replace function ai.grant_to(variadic grantees name[]) returns jsonb
as $func$
    select jsonb_build_object
    ( 'implementation', 'explicit'
    , 'config_type', 'grant_to'
    , 'grant_to', pg_catalog.to_jsonb(grantees)
    )
$func$ language sql immutable security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- _resolve_grant_to_default
create or replace function ai._resolve_grant_to_default() returns jsonb
as $func$
declare
    _setting text;
begin
    select pg_catalog.current_setting('ai.grant_to_default', true) into _setting;
    case _setting
        when 'grant_to_timescale' then
            return ai.grant_to_timescale();
        when 'grant_to' then
            return ai.grant_to();
    end case;
    return ai.grant_to();
end;
$func$ language plpgsql volatile security invoker
set search_path to pg_catalog, pg_temp
;
