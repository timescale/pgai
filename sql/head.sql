
set local search_path = pg_catalog, pg_temp;

/*
if this is the first installation of the extension, create the migration table.
if the extension has already been installed (i.e. we are upgrading), make sure
that the user doing the upgrade is the same user that owns the ai_migration
table. abort the upgrade if different.
*/
do $owner_check$
declare
    _current_user_id oid = null;
    _migration_table_owner_id oid = null;
begin
    select pg_catalog.to_regrole(current_user)::oid
    into strict _current_user_id;

    select k.relowner into _migration_table_owner_id
    from pg_catalog.pg_class k
    inner join pg_catalog.pg_namespace n on (k.relnamespace = n.oid)
    where k.relname = 'ai_migration'
    and n.nspname = '@extschema@';

    if _migration_table_owner_id is not null
    and _migration_table_owner_id is distinct from _current_user_id then
        raise exception 'only the owner of the @extschema@.ai_migration table can upgrade this extension';
    end if;

    if _migration_table_owner_id is null then
        create table @extschema@.ai_migration
        ( "name" text not null primary key
        , applied_at_version text not null
        , applied_at timestamptz not null default clock_timestamp()
        , body text not null
        );
        perform pg_catalog.pg_extension_config_dump('@extschema@.ai_migration'::regclass, '');
    end if;
end;
$owner_check$;

