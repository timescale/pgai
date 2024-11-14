
do language plpgsql $block$
declare
    _filter text;
    _sql text;
begin
    -- two rows are inserted into the ai._secret_permissions table automatically
    -- on extension creation. these two rows should not be dumped as they cause
    -- duplicate key value violations on the pk constraint when restored
    -- the two rows are inserted on extension creation and then again on table
    -- restore. adding a filter so that they don't get dumped should fix the issue
    select pg_catalog.format
    ( $sql$where ("name", "role") not in (('*', 'pg_database_owner'), ('*', %L))$sql$
    , pg_catalog."session_user"()
    ) into strict _filter
    ;

    -- update the filter criteria on the table
    select pg_catalog.format
    ( $sql$select pg_catalog.pg_extension_config_dump('ai._secret_permissions'::pg_catalog.regclass, %L)$sql$
    , _filter
    ) into strict _sql
    ;
    execute _sql;
end;
$block$;
