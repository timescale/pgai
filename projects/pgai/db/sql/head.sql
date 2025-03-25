
set local search_path = pg_catalog, pg_temp;

/*
make sure that the user doing the install/upgrade is the same user who owns the
migration table. abort the upgrade if different.
*/

CREATE SCHEMA IF NOT EXISTS ai;


do $bootstrap_app$
declare
    _current_user_id oid = null;
    _migration_table_owner_id oid = null;
    _database_owner_id oid = null;
begin
    select pg_catalog.to_regrole(current_user)::oid
    into strict _current_user_id;

    select k.relowner into _migration_table_owner_id
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace = n.oid)
    where k.relname operator(pg_catalog.=) 'migration_app'
    and n.nspname operator(pg_catalog.=) 'ai';

    if _migration_table_owner_id is not null
    and _migration_table_owner_id is distinct from _current_user_id then
    
        if _migration_table_owner_id = to_regrole('pg_database_owner') then
            select d.datdba into strict _database_owner_id
            from pg_catalog.pg_database d
            where d.datname = current_database();

            if _database_owner_id is distinct from _current_user_id then
                raise exception 'only the owner of the ai.migration_app table can run database migrations';
                return;
            end if;
        else
            raise exception 'only the owner of the ai.migration_app table can run database migrations';
            return;
        end if;
    end if;

    if _migration_table_owner_id is null then
        create table ai.migration_app
        ( "name" text not null primary key
        , applied_at_version text not null
        , applied_at timestamptz not null default pg_catalog.clock_timestamp()
        , body text not null
        );
    end if;
end;
$bootstrap_app$;

--make sure there is only one install at a time
LOCK TABLE ai.migration_app;

-- records any feature flags that were enabled when installing
-- a prerelease version of the extension
create table if not exists ai.feature_flag_app
( "name" text not null primary key
, applied_at_version text not null
, applied_at timestamptz not null default pg_catalog.clock_timestamp()
);

create table if not exists ai.app_version
( "name" text not null primary key
, version text not null
, installed_at timestamptz not null default pg_catalog.clock_timestamp()
);

--check if the app has already been installed, error if so
do $$
declare
    _app_version text;
begin
    select version from ai.app_version where name operator(pg_catalog.=) 'ai' into _app_version;
    
    if _app_version is not null and _app_version = '__version__' then
        raise exception 'the pgai library has already been installed/upgraded' using errcode = '42710';
    end if;
end;
$$;

insert into ai.app_version ("name", version)
values ('ai', '__version__') on conflict ("name") do update set version = excluded.version;
