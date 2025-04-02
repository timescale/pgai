
set local search_path = pg_catalog, pg_temp;

/*
make sure that the user doing the install/upgrade is the same user who owns the
schema and migration table. abort the upgrade if different.
*/
do $bootstrap_extension$
declare
    _current_user_id oid = null;
    _schema_exists boolean = false;
    _migration_table_owner_id oid = null;
begin
    select pg_catalog.to_regrole('@extowner@')::oid
    into strict _current_user_id;

    select count(*) > 0 into strict _schema_exists
    from pg_catalog.pg_namespace
    where pg_namespace.nspname operator(pg_catalog.=) 'ai';

    if not _schema_exists then
        -- this should NEVER happen
        -- we have `schema=ai` in the control file, so postgres creates the schema automatically
        -- but this line makes pgspot happy
        create schema ai;
    end if;

    select k.relowner into _migration_table_owner_id
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace = n.oid)
    where k.relname operator(pg_catalog.=) 'migration'
    and n.nspname operator(pg_catalog.=) 'ai';

    if _migration_table_owner_id is not null
    and _migration_table_owner_id is distinct from _current_user_id then
        raise exception 'only the owner of the ai.migration table can install/upgrade this extension';
        return;
    end if;

    if _migration_table_owner_id is null then
        create table ai.migration
        ( "name" text not null primary key
        , applied_at_version text not null
        , applied_at timestamptz not null default pg_catalog.clock_timestamp()
        , body text not null
        );
    end if;
end;
$bootstrap_extension$;

-- records any feature flags that were enabled when installing
-- a prerelease version of the extension
create table if not exists ai.feature_flag
( "name" text not null primary key
, applied_at_version text not null
, applied_at timestamptz not null default pg_catalog.clock_timestamp()
);
