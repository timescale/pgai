--------------------------------------------------------------------------------
-- ai 0.10.1


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


-------------------------------------------------------------------------------
-- 002-secret_permissions.sql
do $outer_migration_block$ /*002-secret_permissions.sql*/
declare
    _sql text;
    _migration record;
    _migration_name text = $migration_name$002-secret_permissions.sql$migration_name$;
    _migration_body text =
$migration_body$
create table ai._secret_permissions
( name text not null check(name = '*' or name ~ '^[A-Za-z0-9_.]+$')
, "role" text not null
, primary key (name, "role")
);
-- we add a filter to the dump config in 007-secret_permissions-dump-filter.sql
perform pg_catalog.pg_extension_config_dump('ai._secret_permissions'::pg_catalog.regclass, '');
--only admins will have access to this table
revoke all on ai._secret_permissions from public;

$migration_body$;
begin
    select * into _migration from ai.migration where "name" operator(pg_catalog.=) _migration_name;
    if _migration is not null then
        raise notice 'migration %s already applied. skipping.', _migration_name;
        if _migration.body operator(pg_catalog.!=) _migration_body
            and _migration_name not in ('009-drop-truncate-from-vectorizer-config.sql', '020-divest.sql') then
            raise warning 'the contents of migration "%" have changed', _migration_name;
        end if;
        return;
    end if;
    _sql = pg_catalog.format(E'do /*%s*/ $migration_body$\nbegin\n%s\nend;\n$migration_body$;', _migration_name, _migration_body);
    execute _sql;
    insert into ai.migration ("name", body, applied_at_version)
    values (_migration_name, _migration_body, $version$0.10.1$version$);
end;
$outer_migration_block$;

-------------------------------------------------------------------------------
-- 004-drop_fn_no_api_key_name.sql
do $outer_migration_block$ /*004-drop_fn_no_api_key_name.sql*/
declare
    _sql text;
    _migration record;
    _migration_name text = $migration_name$004-drop_fn_no_api_key_name.sql$migration_name$;
    _migration_body text =
$migration_body$
drop function if exists ai.openai_list_models(text, text);
drop function if exists ai.openai_embed(text, text,  text, text, int, text);
drop function if exists ai.openai_embed(text,integer[],text,text,integer,text);
drop function if exists ai.openai_embed(text,text[],text,text,integer,text);
drop function if exists ai.openai_chat_complete_simple(text,text);
drop function if exists ai.openai_chat_complete(text,jsonb,text,text,double precision,jsonb,boolean,integer,integer,integer,double precision,jsonb,integer,text,double precision,double precision,jsonb,jsonb,text);
drop function if exists ai.openai_moderate(text,text,text,text);
drop function if exists ai.anthropic_generate(text,jsonb,integer,text,text,double precision,integer,text,text,text[],double precision,jsonb,jsonb,integer,double precision);
drop function if exists ai.cohere_chat_complete(text,text,text,text,jsonb,text,text,jsonb,boolean,jsonb,text,double precision,integer,integer,integer,double precision,integer,text[],double precision,double precision,jsonb,jsonb,boolean);
drop function if exists ai.cohere_classify_simple(text,text[],text,jsonb,text);
drop function if exists ai.cohere_classify(text,text[],text,jsonb,text);
drop function if exists ai.cohere_detokenize(text,integer[],text);
drop function if exists ai.cohere_embed(text,text,text,text,text);
drop function if exists ai.cohere_list_models(text,text,boolean);
drop function if exists ai.cohere_rerank_simple(text,text,jsonb,text,integer,integer);
drop function if exists ai.cohere_rerank(text,text,jsonb,text,integer,text[],boolean,integer);
drop function if exists ai.cohere_tokenize(text,text,text);
drop function if exists ai.reveal_secret(text);

$migration_body$;
begin
    select * into _migration from ai.migration where "name" operator(pg_catalog.=) _migration_name;
    if _migration is not null then
        raise notice 'migration %s already applied. skipping.', _migration_name;
        if _migration.body operator(pg_catalog.!=) _migration_body
            and _migration_name not in ('009-drop-truncate-from-vectorizer-config.sql', '020-divest.sql') then
            raise warning 'the contents of migration "%" have changed', _migration_name;
        end if;
        return;
    end if;
    _sql = pg_catalog.format(E'do /*%s*/ $migration_body$\nbegin\n%s\nend;\n$migration_body$;', _migration_name, _migration_body);
    execute _sql;
    insert into ai.migration ("name", body, applied_at_version)
    values (_migration_name, _migration_body, $version$0.10.1$version$);
end;
$outer_migration_block$;

-------------------------------------------------------------------------------
-- 007-secret-permissions-dump-filter.sql
do $outer_migration_block$ /*007-secret-permissions-dump-filter.sql*/
declare
    _sql text;
    _migration record;
    _migration_name text = $migration_name$007-secret-permissions-dump-filter.sql$migration_name$;
    _migration_body text =
$migration_body$

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

$migration_body$;
begin
    select * into _migration from ai.migration where "name" operator(pg_catalog.=) _migration_name;
    if _migration is not null then
        raise notice 'migration %s already applied. skipping.', _migration_name;
        if _migration.body operator(pg_catalog.!=) _migration_body
            and _migration_name not in ('009-drop-truncate-from-vectorizer-config.sql', '020-divest.sql') then
            raise warning 'the contents of migration "%" have changed', _migration_name;
        end if;
        return;
    end if;
    _sql = pg_catalog.format(E'do /*%s*/ $migration_body$\nbegin\n%s\nend;\n$migration_body$;', _migration_name, _migration_body);
    execute _sql;
    insert into ai.migration ("name", body, applied_at_version)
    values (_migration_name, _migration_body, $version$0.10.1$version$);
end;
$outer_migration_block$;

-------------------------------------------------------------------------------
-- 008-drop-ollama-functions-with-keep-alive.sql
do $outer_migration_block$ /*008-drop-ollama-functions-with-keep-alive.sql*/
declare
    _sql text;
    _migration record;
    _migration_name text = $migration_name$008-drop-ollama-functions-with-keep-alive.sql$migration_name$;
    _migration_body text =
$migration_body$
drop function if exists ai.ollama_embed(text, text, text, float8, jsonb);
drop function if exists ai.ollama_generate(text, text, text, bytea[], float8, jsonb, text, text, int[]);
drop function if exists ai.ollama_chat_complete(text, jsonb, text, float8, jsonb);

$migration_body$;
begin
    select * into _migration from ai.migration where "name" operator(pg_catalog.=) _migration_name;
    if _migration is not null then
        raise notice 'migration %s already applied. skipping.', _migration_name;
        if _migration.body operator(pg_catalog.!=) _migration_body
            and _migration_name not in ('009-drop-truncate-from-vectorizer-config.sql', '020-divest.sql') then
            raise warning 'the contents of migration "%" have changed', _migration_name;
        end if;
        return;
    end if;
    _sql = pg_catalog.format(E'do /*%s*/ $migration_body$\nbegin\n%s\nend;\n$migration_body$;', _migration_name, _migration_body);
    execute _sql;
    insert into ai.migration ("name", body, applied_at_version)
    values (_migration_name, _migration_body, $version$0.10.1$version$);
end;
$outer_migration_block$;

-------------------------------------------------------------------------------
-- 009-drop-truncate-from-vectorizer-config.sql
do $outer_migration_block$ /*009-drop-truncate-from-vectorizer-config.sql*/
declare
    _sql text;
    _migration record;
    _migration_name text = $migration_name$009-drop-truncate-from-vectorizer-config.sql$migration_name$;
    _migration_body text =
$migration_body$
DROP FUNCTION IF EXISTS ai.embedding_ollama(text,integer,text,boolean,jsonb,text);
DROP FUNCTION IF EXISTS ai.embedding_voyageai(text,integer,text,booleab,jsonb,text);
DROP FUNCTION IF EXISTS ai.voyageai_embed(text,text,text,boolean,text,text);
DROP FUNCTION IF EXISTS ai.voyageai_embed(text,text[],text,boolean,text,text);

$migration_body$;
begin
    select * into _migration from ai.migration where "name" operator(pg_catalog.=) _migration_name;
    if _migration is not null then
        raise notice 'migration %s already applied. skipping.', _migration_name;
        if _migration.body operator(pg_catalog.!=) _migration_body
            and _migration_name not in ('009-drop-truncate-from-vectorizer-config.sql', '020-divest.sql') then
            raise warning 'the contents of migration "%" have changed', _migration_name;
        end if;
        return;
    end if;
    _sql = pg_catalog.format(E'do /*%s*/ $migration_body$\nbegin\n%s\nend;\n$migration_body$;', _migration_name, _migration_body);
    execute _sql;
    insert into ai.migration ("name", body, applied_at_version)
    values (_migration_name, _migration_body, $version$0.10.1$version$);
end;
$outer_migration_block$;

-------------------------------------------------------------------------------
-- 010-drop-embedding-openai-outdated-function.sql
do $outer_migration_block$ /*010-drop-embedding-openai-outdated-function.sql*/
declare
    _sql text;
    _migration record;
    _migration_name text = $migration_name$010-drop-embedding-openai-outdated-function.sql$migration_name$;
    _migration_body text =
$migration_body$

-- dropping in favour of the new signature (adding base_url param)
drop function if exists ai.embedding_openai(text,integer,text,text);
$migration_body$;
begin
    select * into _migration from ai.migration where "name" operator(pg_catalog.=) _migration_name;
    if _migration is not null then
        raise notice 'migration %s already applied. skipping.', _migration_name;
        if _migration.body operator(pg_catalog.!=) _migration_body
            and _migration_name not in ('009-drop-truncate-from-vectorizer-config.sql', '020-divest.sql') then
            raise warning 'the contents of migration "%" have changed', _migration_name;
        end if;
        return;
    end if;
    _sql = pg_catalog.format(E'do /*%s*/ $migration_body$\nbegin\n%s\nend;\n$migration_body$;', _migration_name, _migration_body);
    execute _sql;
    insert into ai.migration ("name", body, applied_at_version)
    values (_migration_name, _migration_body, $version$0.10.1$version$);
end;
$outer_migration_block$;

-------------------------------------------------------------------------------
-- 011-drop-old-functions.sql
do $outer_migration_block$ /*011-drop-old-functions.sql*/
declare
    _sql text;
    _migration record;
    _migration_name text = $migration_name$011-drop-old-functions.sql$migration_name$;
    _migration_body text =
$migration_body$

-- adding `tools` and `response_format` parameters
drop function if exists ai.ollama_chat_complete(text, jsonb, text, text, jsonb);

-- changing type of `tool_choice` parameter
drop function if exists ai.openai_chat_complete(text, jsonb, text, text, text, float8, jsonb, boolean, int, int, int, float8, jsonb, int, text, float8, float8, jsonb, jsonb, text);
$migration_body$;
begin
    select * into _migration from ai.migration where "name" operator(pg_catalog.=) _migration_name;
    if _migration is not null then
        raise notice 'migration %s already applied. skipping.', _migration_name;
        if _migration.body operator(pg_catalog.!=) _migration_body
            and _migration_name not in ('009-drop-truncate-from-vectorizer-config.sql', '020-divest.sql') then
            raise warning 'the contents of migration "%" have changed', _migration_name;
        end if;
        return;
    end if;
    _sql = pg_catalog.format(E'do /*%s*/ $migration_body$\nbegin\n%s\nend;\n$migration_body$;', _migration_name, _migration_body);
    execute _sql;
    insert into ai.migration ("name", body, applied_at_version)
    values (_migration_name, _migration_body, $version$0.10.1$version$);
end;
$outer_migration_block$;

-------------------------------------------------------------------------------
-- 013-cohere-update.sql
do $outer_migration_block$ /*013-cohere-update.sql*/
declare
    _sql text;
    _migration record;
    _migration_name text = $migration_name$013-cohere-update.sql$migration_name$;
    _migration_body text =
$migration_body$

drop function if exists ai.cohere_chat_complete(text,text,text,text,text,jsonb,text,text,jsonb,boolean,jsonb,text,double precision,integer,integer,integer,double precision,integer,text[],double precision,double precision,jsonb,jsonb,boolean);
drop function if exists ai.cohere_rerank_simple(text,text,jsonb,text,text,integer,integer);
drop function if exists ai.cohere_rerank(text,text,jsonb,text,text,integer,text[],boolean,integer);

$migration_body$;
begin
    select * into _migration from ai.migration where "name" operator(pg_catalog.=) _migration_name;
    if _migration is not null then
        raise notice 'migration %s already applied. skipping.', _migration_name;
        if _migration.body operator(pg_catalog.!=) _migration_body
            and _migration_name not in ('009-drop-truncate-from-vectorizer-config.sql', '020-divest.sql') then
            raise warning 'the contents of migration "%" have changed', _migration_name;
        end if;
        return;
    end if;
    _sql = pg_catalog.format(E'do /*%s*/ $migration_body$\nbegin\n%s\nend;\n$migration_body$;', _migration_name, _migration_body);
    execute _sql;
    insert into ai.migration ("name", body, applied_at_version)
    values (_migration_name, _migration_body, $version$0.10.1$version$);
end;
$outer_migration_block$;

-------------------------------------------------------------------------------
-- 014-extra-openai-args.sql
do $outer_migration_block$ /*014-extra-openai-args.sql*/
declare
    _sql text;
    _migration record;
    _migration_name text = $migration_name$014-extra-openai-args.sql$migration_name$;
    _migration_body text =
$migration_body$
drop function if exists ai.openai_list_models(text, text, text);
drop function if exists ai.openai_embed(text, text, text, text, text, int, text);
drop function if exists ai.openai_embed(text, text [], text, text, text, int, text);
drop function if exists ai.openai_embed(text, int [], text, text, text, int, text);
drop function if exists ai.openai_chat_complete(
    text,
    jsonb,
    text,
    text,
    text,
    float8,
    jsonb,
    boolean,
    int,
    int,
    int,
    float8,
    jsonb,
    int,
    text,
    float8,
    float8,
    jsonb,
    text,
    text
);
drop function if exists ai.openai_moderate(text, text, text, text, text);
drop function if exists ai.openai_chat_complete_simple(text, text, text);

$migration_body$;
begin
    select * into _migration from ai.migration where "name" operator(pg_catalog.=) _migration_name;
    if _migration is not null then
        raise notice 'migration %s already applied. skipping.', _migration_name;
        if _migration.body operator(pg_catalog.!=) _migration_body
            and _migration_name not in ('009-drop-truncate-from-vectorizer-config.sql', '020-divest.sql') then
            raise warning 'the contents of migration "%" have changed', _migration_name;
        end if;
        return;
    end if;
    _sql = pg_catalog.format(E'do /*%s*/ $migration_body$\nbegin\n%s\nend;\n$migration_body$;', _migration_name, _migration_body);
    execute _sql;
    insert into ai.migration ("name", body, applied_at_version)
    values (_migration_name, _migration_body, $version$0.10.1$version$);
end;
$outer_migration_block$;

-------------------------------------------------------------------------------
-- 015-openai-chat-complete-max-completion-tokens-arg.sql
do $outer_migration_block$ /*015-openai-chat-complete-max-completion-tokens-arg.sql*/
declare
    _sql text;
    _migration record;
    _migration_name text = $migration_name$015-openai-chat-complete-max-completion-tokens-arg.sql$migration_name$;
    _migration_body text =
$migration_body$
drop function if exists ai.openai_chat_complete(
    text,
    jsonb,
    text,
    text,
    text,
    float8,
    jsonb,
    boolean,
    int,
    int,
    int,
    float8,
    jsonb,
    int,
    text,
    float8,
    float8,
    jsonb,
    text,
    text,
    jsonb,
    jsonb,
    jsonb,
    float8
);
drop function if exists openai_chat_complete_with_raw_response(
    text,
    jsonb,
    text,
    text,
    text,
    float8,
    jsonb,
    boolean,
    int,
    int,
    int,
    float8,
    jsonb,
    int,
    text,
    float8,
    float8,
    jsonb,
    text,
    text,
    jsonb,
    jsonb,
    jsonb,
    float8
);
$migration_body$;
begin
    select * into _migration from ai.migration where "name" operator(pg_catalog.=) _migration_name;
    if _migration is not null then
        raise notice 'migration %s already applied. skipping.', _migration_name;
        if _migration.body operator(pg_catalog.!=) _migration_body
            and _migration_name not in ('009-drop-truncate-from-vectorizer-config.sql', '020-divest.sql') then
            raise warning 'the contents of migration "%" have changed', _migration_name;
        end if;
        return;
    end if;
    _sql = pg_catalog.format(E'do /*%s*/ $migration_body$\nbegin\n%s\nend;\n$migration_body$;', _migration_name, _migration_body);
    execute _sql;
    insert into ai.migration ("name", body, applied_at_version)
    values (_migration_name, _migration_body, $version$0.10.1$version$);
end;
$outer_migration_block$;

-------------------------------------------------------------------------------
-- 016-add-verbose-args.sql
do $outer_migration_block$ /*016-add-verbose-args.sql*/
declare
    _sql text;
    _migration record;
    _migration_name text = $migration_name$016-add-verbose-args.sql$migration_name$;
    _migration_body text =
$migration_body$
-- add verbose boolean to all model calling functions

-- drop all functions that have verbose args before the arg was added.
-- list generated by the following query:
-- SELECT 'DROP FUNCTION IF EXISTS ' || ns.nspname || '.' || proname || '(' || 
--   array_to_string(proargtypes[0:array_length(proargtypes, 1)-2]::regtype[], ', ') || ');' as drop_command 
-- FROM pg_proc p 
-- JOIN pg_namespace ns ON p.pronamespace = ns.oid 
-- WHERE proargnames @> ARRAY['verbose'];

DROP FUNCTION IF EXISTS ai.openai_chat_complete(text, jsonb, text, text, text, double precision, jsonb, boolean, integer, integer, integer, integer, double precision, jsonb, integer, text, double precision, double precision, jsonb, text, text, jsonb, jsonb, jsonb, double precision);
DROP FUNCTION IF EXISTS ai.openai_list_models(text, text, text, jsonb, jsonb, double precision);
DROP FUNCTION IF EXISTS ai.openai_list_models_with_raw_response(text, text, text, jsonb, jsonb, double precision);
DROP FUNCTION IF EXISTS ai.openai_embed(text, text, text, text, text, integer, text, jsonb, jsonb, jsonb, double precision);
DROP FUNCTION IF EXISTS ai.openai_embed(text, text[], text, text, text, integer, text, jsonb, jsonb, jsonb, double precision);
DROP FUNCTION IF EXISTS ai.openai_embed(text, integer[], text, text, text, integer, text, jsonb, jsonb, jsonb, double precision);
DROP FUNCTION IF EXISTS ai.openai_embed_with_raw_response(text, text, text, text, text, integer, text, jsonb, jsonb, jsonb, double precision);
DROP FUNCTION IF EXISTS ai.openai_embed_with_raw_response(text, text[], text, text, text, integer, text, jsonb, jsonb, jsonb, double precision);
DROP FUNCTION IF EXISTS ai.openai_embed_with_raw_response(text, integer[], text, text, text, integer, text, jsonb, jsonb, jsonb, double precision);
DROP FUNCTION IF EXISTS ai.openai_chat_complete_with_raw_response(text, jsonb, text, text, text, double precision, jsonb, boolean, integer, integer, integer, integer, double precision, jsonb, integer, text, double precision, double precision, jsonb, text, text, jsonb, jsonb, jsonb, double precision);
DROP FUNCTION IF EXISTS ai.openai_chat_complete_simple(text, text, text);
DROP FUNCTION IF EXISTS ai.openai_moderate(text, text, text, text, text, jsonb, jsonb, jsonb, double precision);
DROP FUNCTION IF EXISTS ai.openai_moderate_with_raw_response(text, text, text, text, text, jsonb, jsonb, jsonb, double precision);
DROP FUNCTION IF EXISTS ai.ollama_list_models(text);
DROP FUNCTION IF EXISTS ai.ollama_ps(text);
DROP FUNCTION IF EXISTS ai.ollama_embed(text, text, text, text, jsonb);
DROP FUNCTION IF EXISTS ai.ollama_generate(text, text, text, bytea[], text, jsonb, text, text, integer[]);
DROP FUNCTION IF EXISTS ai.ollama_chat_complete(text, jsonb, text, text, jsonb, jsonb, jsonb);
DROP FUNCTION IF EXISTS ai.anthropic_list_models(text, text, text);
DROP FUNCTION IF EXISTS ai.anthropic_generate(text, jsonb, integer, text, text, text, double precision, integer, text, text, text[], double precision, jsonb, jsonb, integer, double precision);
DROP FUNCTION IF EXISTS ai.cohere_list_models(text, text, text, boolean);
DROP FUNCTION IF EXISTS ai.cohere_tokenize(text, text, text, text);
DROP FUNCTION IF EXISTS ai.cohere_detokenize(text, integer[], text, text);
DROP FUNCTION IF EXISTS ai.cohere_embed(text, text, text, text, text, text);
DROP FUNCTION IF EXISTS ai.cohere_classify(text, text[], text, text, jsonb, text);
DROP FUNCTION IF EXISTS ai.cohere_classify_simple(text, text[], text, text, jsonb, text);
DROP FUNCTION IF EXISTS ai.cohere_rerank(text, text, text[], text, text, integer, integer);
DROP FUNCTION IF EXISTS ai.cohere_rerank_simple(text, text, text[], text, text, integer, integer);
DROP FUNCTION IF EXISTS ai.cohere_chat_complete(text, jsonb, text, text, jsonb, jsonb, jsonb, jsonb, text, integer, text[], double precision, integer, double precision, double precision, integer, double precision, boolean, text, boolean);
DROP FUNCTION IF EXISTS ai.voyageai_embed(text, text, text, text, text);
DROP FUNCTION IF EXISTS ai.voyageai_embed(text, text[], text, text, text);
DROP FUNCTION IF EXISTS ai.litellm_embed(text, text, text, text, jsonb);
DROP FUNCTION IF EXISTS ai.litellm_embed(text, text[], text, text, jsonb);
$migration_body$;
begin
    select * into _migration from ai.migration where "name" operator(pg_catalog.=) _migration_name;
    if _migration is not null then
        raise notice 'migration %s already applied. skipping.', _migration_name;
        if _migration.body operator(pg_catalog.!=) _migration_body
            and _migration_name not in ('009-drop-truncate-from-vectorizer-config.sql', '020-divest.sql') then
            raise warning 'the contents of migration "%" have changed', _migration_name;
        end if;
        return;
    end if;
    _sql = pg_catalog.format(E'do /*%s*/ $migration_body$\nbegin\n%s\nend;\n$migration_body$;', _migration_name, _migration_body);
    execute _sql;
    insert into ai.migration ("name", body, applied_at_version)
    values (_migration_name, _migration_body, $version$0.10.1$version$);
end;
$outer_migration_block$;

-------------------------------------------------------------------------------
-- 020-divest.sql
do $outer_migration_block$ /*020-divest.sql*/
declare
    _sql text;
    _migration record;
    _migration_name text = $migration_name$020-divest.sql$migration_name$;
    _migration_body text =
$migration_body$
do $block$
declare
    _vectorizer_is_in_extension boolean;
    _rec record;
    _sql text;
    _db_owner_name text;
    _acl_is_default boolean;
    _major_version integer;
    _maintain text;
begin
    select split_part(current_setting('server_version'), '.', 1)::INT into _major_version   ;
    if _major_version < 17 then
        _maintain := '';
    else
        _maintain := ',MAINTAIN';
    end if;

    --the vectorizer table is in the very first migration that used to be run as part of the extension install
    --so we can check if the vectorizer machinery is in the extension by checking if the vectorizer table exists
    select
        count(*) > 0 into _vectorizer_is_in_extension
    from pg_catalog.pg_depend d
    inner join pg_catalog.pg_class k on (d.objid = k.oid)
    inner join pg_catalog.pg_namespace n on (k.relnamespace = n.oid)
    inner join pg_catalog.pg_extension x on (d.refobjid = x.oid)
    where d.classid = 'pg_catalog.pg_class'::regclass::oid
    and d.refclassid = 'pg_catalog.pg_extension'::regclass::oid
    and d.deptype = 'e'
    and x.extname = 'ai'
    and n.nspname = 'ai'
    and k.relname = 'vectorizer';
    
    if not _vectorizer_is_in_extension then
        --the vectorizer machinery is not in the extension, so we can skip the divest process
        return;
    end if;
    
    drop function if exists ai._vectorizer_create_dependencies(integer);
    drop function if exists ai._vectorizer_handle_drops() cascade;
    
    select r.rolname into strict _db_owner_name
    from pg_catalog.pg_database d
    join pg_catalog.pg_authid r on d.datdba = r.oid
    where d.datname = current_database();

-------------------------------------------------------------------------------
-- schema, tables, views, sequences

    execute format('alter schema ai owner to %I;', _db_owner_name);
    
    execute format('create table ai.pgai_lib_migration
    ( "name" text not null primary key
    , applied_at_version text not null
    , applied_at timestamptz not null default pg_catalog.clock_timestamp()
    , body text not null
    )');
    
    execute format('alter table ai.pgai_lib_migration owner to %I', _db_owner_name);
    execute format('alter extension ai drop table ai.pgai_lib_migration');

    insert into ai.pgai_lib_migration (name, applied_at_version, applied_at, body)
    select "name", 'unpackaged', now(), body
    from ai.migration
    where name in (
        '001-vectorizer.sql'
        , '003-vec-storage.sql'
        , '005-vectorizer-queue-pending.sql'
        , '006-drop-vectorizer.sql'
        --, '009-drop-truncate-from-vectorizer-config.sql' --not included on purpose since it's not the same
        , '012-add-vectorizer-disabled-column.sql'
        , '017-upgrade-source-pk.sql'
        , '018-drop-foreign-key-constraint.sql'
    );

    for _rec in
    (
        select
          n.nspname
        , k.relname
        , k.oid
        , k.relkind
        from pg_catalog.pg_depend d
        inner join pg_catalog.pg_class k on (d.objid = k.oid)
        inner join pg_catalog.pg_namespace n on (k.relnamespace = n.oid)
        inner join pg_catalog.pg_extension x on (d.refobjid = x.oid)
        where d.classid = 'pg_catalog.pg_class'::regclass::oid
        and d.refclassid = 'pg_catalog.pg_extension'::regclass::oid
        and d.deptype = 'e'
        and x.extname = 'ai'
        and (n.nspname, k.relname) in
        (
            values
              ('ai', 'vectorizer_id_seq')
            , ('ai', 'vectorizer')
            , ('ai', 'vectorizer_errors')
            , ('ai', 'vectorizer_status')
        )
    )
    loop
        select format
        ( $sql$alter extension ai drop %s %I.%I$sql$
        , case _rec.relkind
            when 'r' then 'table'
            when 'S' then 'sequence'
            when 'v' then 'view'
          end
        , _rec.nspname
        , _rec.relname
        ) into strict _sql
        ;
        raise notice '%', _sql;
        execute _sql;
        
        -- The sequence vectorizer_id_seq is linked to the table vectorizer, so we cannot change the owner independently.
        -- Changing the owner of the table is sufficient. also we handle the vectorizer table separately below(see comments).
        if _rec.relname != 'vectorizer_id_seq' and _rec.relname != 'vectorizer' THEN
            select format
            ( $sql$alter %s %I.%I owner to %I$sql$
            , case _rec.relkind
                when 'r' then 'table'
                when 'S' then 'sequence'
                when 'v' then 'view'
            end
            , _rec.nspname
            , _rec.relname
            , _db_owner_name
            ) into strict _sql
            ;
            raise notice '%', _sql;
            execute _sql;
        end if;
        
        --for the vectorizer table, we need to change the owner to pg_database_owner and then to the db owner
        --this seems strange, but it's done to reassign the granted options from pg_database_owner to the db owner
        execute format('alter table ai.vectorizer owner to pg_database_owner');
        execute format('alter table ai.vectorizer owner to %I', _db_owner_name);
      
        --see if the default acl is set for the db owner and reset to null if so 
        if _rec.relkind in ('r', 'v') then
            select relacl = array[ 
               makeaclitem(
                to_regrole(_db_owner_name)::oid, 
                to_regrole(_db_owner_name)::oid, 
                'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER' || _maintain, 
                TRUE),
                makeaclitem(
                to_regrole('pg_database_owner')::oid, 
                to_regrole(_db_owner_name)::oid, 
                'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER' || _maintain, 
                TRUE)
            ] into _acl_is_default
            from pg_catalog.pg_class c
            where c.oid = _rec.oid;
            
            if _acl_is_default then
                execute format('update pg_catalog.pg_class set relacl = NULL where oid = %L', _rec.oid);
            end if;
        end if;
    end loop;
    
    --check the vectorizer_id_seq acl and reset to null if it is the default (do this after the loop so we can see acl after the tables are changed)
    select  c.relacl = 
       array[
           makeaclitem(to_regrole(_db_owner_name)::oid, to_regrole(_db_owner_name)::oid, 'SELECT, USAGE, UPDATE', TRUE)
        ] 
    into _acl_is_default
    from pg_catalog.pg_class c
    where c.oid = to_regclass('ai.vectorizer_id_seq');
    
    if _acl_is_default is not null and _acl_is_default then
        execute format('update pg_catalog.pg_class set relacl = NULL where oid = %L', to_regclass('ai.vectorizer_id_seq')::oid);
    end if;
    
    --vectorizer had a grant option for the db owner, but now the db owner is the table owner so clean up the acl by removing the grant option
    select c.relacl @> 
           makeaclitem(
            to_regrole(_db_owner_name)::oid, 
            to_regrole(_db_owner_name)::oid, 
            'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER' || _maintain, 
            TRUE) into _acl_is_default
    from pg_catalog.pg_class c
    where c.oid = to_regclass('ai.vectorizer');
    
    if _acl_is_default is not null and _acl_is_default then
        execute format('revoke grant option for all on ai.vectorizer from %I', _db_owner_name);
    end if;
    

-------------------------------------------------------------------------------
-- triggers

--nothing to do?

-------------------------------------------------------------------------------
-- event triggers

--no event triggers left

-------------------------------------------------------------------------------
-- functions, procedures
    for _rec in
    (
        select *
        from
        (
            select format
            ( $sql$%s %I.%I(%s)$sql$
            , case when p.prokind = 'f' then 'function' else 'procedure' end
            , n.nspname
            , p.proname
            , pg_catalog.pg_get_function_identity_arguments(p.oid)
            ) as spec
            , p.oid
            from pg_catalog.pg_depend d
            inner join pg_catalog.pg_proc p on (d.objid = p.oid)
            inner join pg_catalog.pg_namespace n on (p.pronamespace = n.oid)
            inner join pg_catalog.pg_extension x on (d.refobjid = x.oid)
            where d.classid = 'pg_catalog.pg_proc'::regclass::oid
            and d.refclassid = 'pg_catalog.pg_extension'::regclass::oid
            and d.deptype = 'e'
            and x.extname = 'ai'
        ) x
        where x.spec in
        ( 
         'function ai.chunking_character_text_splitter(chunk_column name, chunk_size integer, chunk_overlap integer, separator text, is_separator_regex boolean)'
        , 'function ai.chunking_recursive_character_text_splitter(chunk_column name, chunk_size integer, chunk_overlap integer, separators text[], is_separator_regex boolean)'
        , 'function ai._validate_chunking(config jsonb, source_schema name, source_table name)'
        , 'function ai.formatting_python_template(template text)'
        , 'function ai._validate_formatting_python_template(config jsonb, source_schema name, source_table name)'
        , 'function ai._validate_formatting(config jsonb, source_schema name, source_table name)'
        , 'function ai.scheduling_none()'
        , 'function ai.scheduling_default()'
        , 'function ai.scheduling_timescaledb(schedule_interval interval, initial_start timestamp with time zone, fixed_schedule boolean, timezone text)'
        , 'function ai._resolve_scheduling_default()'
        , 'function ai._validate_scheduling(config jsonb)'
        , 'function ai.embedding_openai(model text, dimensions integer, chat_user text, api_key_name text, base_url text)'
        , 'function ai.embedding_ollama(model text, dimensions integer, base_url text, options jsonb, keep_alive text)'
        , 'function ai.embedding_voyageai(model text, dimensions integer, input_type text, api_key_name text)'
        , 'function ai.embedding_litellm(model text, dimensions integer, api_key_name text, extra_options jsonb)'
        , 'function ai._validate_embedding(config jsonb)'
        , 'function ai.indexing_none()'
        , 'function ai.indexing_default()'
        , 'function ai.indexing_diskann(min_rows integer, storage_layout text, num_neighbors integer, search_list_size integer, max_alpha double precision, num_dimensions integer, num_bits_per_dimension integer, create_when_queue_empty boolean)'
        , 'function ai._resolve_indexing_default()'
        , 'function ai._validate_indexing_diskann(config jsonb)'
        , 'function ai.indexing_hnsw(min_rows integer, opclass text, m integer, ef_construction integer, create_when_queue_empty boolean)'
        , 'function ai._validate_indexing_hnsw(config jsonb)'
        , 'function ai._validate_indexing(config jsonb)'
        , 'function ai.processing_default(batch_size integer, concurrency integer)'
        , 'function ai._validate_processing(config jsonb)'
        , 'function ai.grant_to(VARIADIC grantees name[])'
        , 'function ai.grant_to()'
        , 'function ai._vectorizer_source_pk(source_table regclass)'
        , 'function ai._vectorizer_grant_to_source(source_schema name, source_table name, grant_to name[])'
        , 'function ai._vectorizer_grant_to_vectorizer(grant_to name[])'
        , 'function ai._vectorizer_create_target_table(source_pk jsonb, target_schema name, target_table name, dimensions integer, grant_to name[])'
        , 'function ai._vectorizer_create_view(view_schema name, view_name name, source_schema name, source_table name, source_pk jsonb, target_schema name, target_table name, grant_to name[])'
        , 'function ai._vectorizer_create_queue_table(queue_schema name, queue_table name, source_pk jsonb, grant_to name[])'
        , 'function ai._vectorizer_build_trigger_definition(queue_schema name, queue_table name, target_schema name, target_table name, source_pk jsonb)'
        , 'function ai._vectorizer_create_source_trigger(trigger_name name, queue_schema name, queue_table name, source_schema name, source_table name, target_schema name, target_table name, source_pk jsonb)'
        , 'function ai._vectorizer_create_source_trigger(trigger_name name, queue_schema name, queue_table name, source_schema name, source_table name, source_pk jsonb)'
        , 'function ai._vectorizer_create_target_table(source_schema name, source_table name, source_pk jsonb, target_schema name, target_table name, dimensions integer, grant_to name[])'
        , 'function ai.drop_vectorizer(vectorizer_id integer)'
        , 'function ai.vectorizer_queue_pending(vectorizer_id integer)'
        , 'function ai._vectorizer_vector_index_exists(target_schema name, target_table name, indexing jsonb)'
        , 'function ai._vectorizer_should_create_vector_index(vectorizer ai.vectorizer)'
        , 'function ai._vectorizer_create_vector_index(target_schema name, target_table name, indexing jsonb)'
        , 'procedure ai._vectorizer_job(IN job_id integer, IN config jsonb)'
        , 'function ai._vectorizer_schedule_job(vectorizer_id integer, scheduling jsonb)'
        , 'function ai.create_vectorizer(source regclass, destination name, embedding jsonb, chunking jsonb, indexing jsonb, formatting jsonb, scheduling jsonb, processing jsonb, target_schema name, target_table name, view_schema name, view_name name, queue_schema name, queue_table name, grant_to name[], enqueue_existing boolean)'
        , 'function ai.disable_vectorizer_schedule(vectorizer_id integer)'
        , 'function ai.enable_vectorizer_schedule(vectorizer_id integer)'
        , 'function ai.drop_vectorizer(vectorizer_id integer, drop_all boolean)'
        , 'function ai.vectorizer_queue_pending(vectorizer_id integer, exact_count boolean)'
        , 'function ai.vectorizer_embed(embedding_config jsonb, input_text text, input_type text)'
        , 'function ai.vectorizer_embed(vectorizer_id integer, input_text text, input_type text)'
        )
    )
    loop
        select format
        ( $sql$alter extension ai drop %s$sql$
        , _rec.spec
        ) into strict _sql
        ;
        raise notice '%', _sql;
        execute _sql;
        
        select format
        ( $sql$alter %s owner to %I$sql$
        , _rec.spec
        , _db_owner_name
        ) into strict _sql
        ;
        raise notice '%', _sql;
        execute _sql;
        
        --see if the default acl is set for the db owner and reset to null if so 
        select proacl = array[ 
           makeaclitem(
            to_regrole(_db_owner_name)::oid, 
            to_regrole(_db_owner_name)::oid, 
            'EXECUTE', 
            TRUE),
            makeaclitem(
            to_regrole('pg_database_owner')::oid, 
            to_regrole(_db_owner_name)::oid, 
            'EXECUTE', 
            TRUE)
        ] into _acl_is_default
        from pg_catalog.pg_proc p
        where p.oid = _rec.oid;
        
        if _acl_is_default then
            execute format('update pg_catalog.pg_proc set proacl = NULL where oid = %L', _rec.oid);
        end if;
    end loop;
end;
$block$;

$migration_body$;
begin
    select * into _migration from ai.migration where "name" operator(pg_catalog.=) _migration_name;
    if _migration is not null then
        raise notice 'migration %s already applied. skipping.', _migration_name;
        if _migration.body operator(pg_catalog.!=) _migration_body
            and _migration_name not in ('009-drop-truncate-from-vectorizer-config.sql', '020-divest.sql') then
            raise warning 'the contents of migration "%" have changed', _migration_name;
        end if;
        return;
    end if;
    _sql = pg_catalog.format(E'do /*%s*/ $migration_body$\nbegin\n%s\nend;\n$migration_body$;', _migration_name, _migration_body);
    execute _sql;
    insert into ai.migration ("name", body, applied_at_version)
    values (_migration_name, _migration_body, $version$0.10.1$version$);
end;
$outer_migration_block$;

--------------------------------------------------------------------------------
-- 001-openai.sql

-------------------------------------------------------------------------------
-- openai_tokenize
-- encode text as tokens for a given model
-- https://github.com/openai/tiktoken/blob/main/README.md
create or replace function ai.openai_tokenize(model text, text_input text) returns int[]
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import tiktoken
    encoding = tiktoken.encoding_for_model(model)
    tokens = encoding.encode(text_input)
    return tokens
$python$
language plpython3u strict immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_detokenize
-- decode tokens for a given model back into text
-- https://github.com/openai/tiktoken/blob/main/README.md
create or replace function ai.openai_detokenize(model text, tokens int[]) returns text
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import tiktoken
    encoding = tiktoken.encoding_for_model(model)
    content = encoding.decode(tokens)
    return content
$python$
language plpython3u strict immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_list_models
-- list models supported on the openai platform
-- https://platform.openai.com/docs/api-reference/models/list
create or replace function ai.openai_list_models
( api_key text default null
, api_key_name text default null
, extra_headers jsonb default null
, extra_query jsonb default null
, verbose boolean default false
, client_config jsonb default null
)
returns table
( id text
, created timestamptz
, owned_by text
)
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.openai
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.openai.DEFAULT_KEY_NAME, SD)
    with ai.utils.VerboseRequestTrace(plpy, "openai.list_models()", verbose):
        models = ai.openai.list_models(
            plpy,
            api_key_resolved,
            ai.openai.str_arg_to_dict(client_config),
            extra_headers,
            extra_query)
    for tup in models:
        yield tup
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;


-------------------------------------------------------------------------------
-- openai_list_models_with_raw_response
-- list models supported on the openai platform
-- https://platform.openai.com/docs/api-reference/models/list
create or replace function ai.openai_list_models_with_raw_response
( api_key text default null
, api_key_name text default null
, extra_headers jsonb default null
, extra_query jsonb default null
, verbose boolean default false
, client_config jsonb default null
)
returns jsonb
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.openai
    import ai.secrets
    import ai.utils
    from datetime import datetime, timezone

    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.openai.DEFAULT_KEY_NAME, SD)
    client = ai.openai.make_client(plpy, api_key, ai.openai.str_arg_to_dict(client_config))

    kwargs = ai.openai.create_kwargs(
        extra_headers=ai.openai.str_arg_to_dict(extra_headers),
        extra_query=ai.openai.str_arg_to_dict(extra_query),
    )

    with ai.utils.VerboseRequestTrace(plpy, "openai.list_models()", verbose):
        return client.models.with_raw_response.list(**kwargs).text
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed
-- generate an embedding from a text value
-- https://platform.openai.com/docs/api-reference/embeddings/create
create or replace function ai.openai_embed
( model text
, input_text text
, api_key text default null
, api_key_name text default null
, dimensions int default null
, openai_user text default null
, extra_headers jsonb default null
, extra_query jsonb default null
, extra_body jsonb default null
, verbose boolean default false
, client_config jsonb default null
) returns @extschema:vector@.vector
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.openai
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.openai.DEFAULT_KEY_NAME, SD)
    with ai.utils.VerboseRequestTrace(plpy, "openai.embed()", verbose):
        embeddings = ai.openai.embed(
            plpy,
            ai.openai.str_arg_to_dict(client_config),
            model,
            input_text,
            api_key_resolved,
            dimensions,
            openai_user,
            extra_headers,
            extra_query,
            extra_body)
    for tup in embeddings:
        return tup[1]
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed
-- generate embeddings from an array of text values
-- https://platform.openai.com/docs/api-reference/embeddings/create
create or replace function ai.openai_embed
( model text
, input_texts text[]
, api_key text default null
, api_key_name text default null
, dimensions int default null
, openai_user text default null
, extra_headers jsonb default null
, extra_query jsonb default null
, extra_body jsonb default null
, verbose boolean default false
, client_config jsonb default null
) returns table
( "index" int
, embedding @extschema:vector@.vector
)
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.openai
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.openai.DEFAULT_KEY_NAME, SD)
    with ai.utils.VerboseRequestTrace(plpy, "openai.embed()", verbose):
        embeddings = ai.openai.embed(
            plpy,
            ai.openai.str_arg_to_dict(client_config),
            model,
            input_texts,
            api_key_resolved,
            dimensions,
            openai_user,
            extra_headers,
            extra_query,
            extra_body)
    for tup in embeddings:
        yield tup
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed
-- generate embeddings from an array of tokens
-- https://platform.openai.com/docs/api-reference/embeddings/create
create or replace function ai.openai_embed
( model text
, input_tokens int[]
, api_key text default null
, api_key_name text default null
, dimensions int default null
, openai_user text default null
, extra_headers jsonb default null
, extra_query jsonb default null
, extra_body jsonb default null
, verbose boolean default false
, client_config jsonb default null
) returns @extschema:vector@.vector
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.openai
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.openai.DEFAULT_KEY_NAME, SD)
    with ai.utils.VerboseRequestTrace(plpy, "openai.embed()", verbose):
        embeddings = ai.openai.embed(
            plpy,
            ai.openai.str_arg_to_dict(client_config),
            model,
            input_tokens,
            api_key_resolved,
            dimensions,
            openai_user,
            extra_headers,
            extra_query,
            extra_body)
    for tup in embeddings:
        return tup[1]
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;


-------------------------------------------------------------------------------
-- openai_embed_with_raw_response
-- generate an embedding from a text value
-- https://platform.openai.com/docs/api-reference/embeddings/create
create or replace function ai.openai_embed_with_raw_response
( model text
, input_text text
, api_key text default null
, api_key_name text default null
, dimensions int default null
, openai_user text default null
, extra_headers jsonb default null
, extra_query jsonb default null
, extra_body jsonb default null
, verbose boolean default false
, client_config jsonb default null
) returns jsonb
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.openai
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.openai.DEFAULT_KEY_NAME, SD)
    with ai.utils.VerboseRequestTrace(plpy, "openai.embed()", verbose):
        return ai.openai.embed_with_raw_response(
            plpy,
            ai.openai.str_arg_to_dict(client_config),
            model,
            input_text,
            api_key_resolved,
            dimensions,
            openai_user,
            extra_headers,
            extra_query,
            extra_body)
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed_with_raw_response
-- generate embeddings from an array of text values
-- https://platform.openai.com/docs/api-reference/embeddings/create
create or replace function ai.openai_embed_with_raw_response
( model text
, input_texts text[]
, api_key text default null
, api_key_name text default null
, dimensions int default null
, openai_user text default null
, extra_headers jsonb default null
, extra_query jsonb default null
, extra_body jsonb default null
, verbose boolean default false
, client_config jsonb default null
) returns jsonb
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.openai
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.openai.DEFAULT_KEY_NAME, SD)
    with ai.utils.VerboseRequestTrace(plpy, "openai.embed()", verbose):
        return ai.openai.embed_with_raw_response(
            plpy,
            ai.openai.str_arg_to_dict(client_config),
            model,
            input_texts,
            api_key_resolved,
            dimensions,
            openai_user,
            extra_headers,
            extra_query,
            extra_body)
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_embed_with_raw_response
-- generate embeddings from an array of tokens
-- https://platform.openai.com/docs/api-reference/embeddings/create
create or replace function ai.openai_embed_with_raw_response
( model text
, input_tokens int[]
, api_key text default null
, api_key_name text default null
, dimensions int default null
, openai_user text default null
, extra_headers jsonb default null
, extra_query jsonb default null
, extra_body jsonb default null
, verbose boolean default false
, client_config jsonb default null
) returns jsonb
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.openai
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.openai.DEFAULT_KEY_NAME, SD)
    with ai.utils.VerboseRequestTrace(plpy, "openai.embed()", verbose):
        return ai.openai.embed_with_raw_response(
            plpy,
            ai.openai.str_arg_to_dict(client_config),
            model,
            input_tokens,
            api_key_resolved,
            dimensions,
            openai_user,
            extra_headers,
            extra_query,
            extra_body)
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_chat_complete
-- text generation / chat completion
-- https://platform.openai.com/docs/api-reference/chat/create
create or replace function ai.openai_chat_complete
( model text
, messages jsonb
, api_key text default null
, api_key_name text default null
, frequency_penalty float8 default null
, logit_bias jsonb default null
, logprobs boolean default null
, top_logprobs int default null
, max_tokens int default null
, max_completion_tokens int default null
, n int default null
, presence_penalty float8 default null
, response_format jsonb default null
, seed int default null
, stop text default null
, temperature float8 default null
, top_p float8 default null
, tools jsonb default null
, tool_choice text default null
, openai_user text default null
, extra_headers jsonb default null
, extra_query jsonb default null
, extra_body jsonb default null
, verbose boolean default false
, client_config jsonb default null
) returns jsonb
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.openai
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.openai.DEFAULT_KEY_NAME, SD)
    client = ai.openai.make_client(plpy, api_key_resolved, ai.openai.str_arg_to_dict(client_config))
    import json

    messages_1 = json.loads(messages)
    if not isinstance(messages_1, list):
        plpy.error("messages is not an array")

    kwargs = ai.openai.create_kwargs(
        frequency_penalty=frequency_penalty,
        logit_bias=ai.openai.str_arg_to_dict(logit_bias),
        logprobs=logprobs,
        top_logprobs=top_logprobs,
        max_tokens=max_tokens,
        max_completion_tokens=max_completion_tokens,
        n=n,
        presence_penalty=presence_penalty,
        response_format=ai.openai.str_arg_to_dict(response_format),
        seed=seed,
        stop=stop,
        temperature=temperature,
        top_p=top_p,
        tools=ai.openai.str_arg_to_dict(tools),
        tool_choice=tool_choice if tool_choice in {'auto', 'none', 'required'} else ai.openai.str_arg_to_dict(tool_choice),
        user=openai_user,
        extra_headers=ai.openai.str_arg_to_dict(extra_headers),
        extra_query=ai.openai.str_arg_to_dict(extra_query),
        extra_body=ai.openai.str_arg_to_dict(extra_body))

    with ai.utils.VerboseRequestTrace(plpy, "openai.chat_complete()", verbose):
        response = client.chat.completions.create(
          model=model
        , messages=messages_1
        , stream=False
        , **kwargs
        )

    return response.model_dump_json()
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_chat_complete_with_raw_response
-- text generation / chat completion
-- https://platform.openai.com/docs/api-reference/chat/create
create or replace function ai.openai_chat_complete_with_raw_response
( model text
, messages jsonb
, api_key text default null
, api_key_name text default null
, frequency_penalty float8 default null
, logit_bias jsonb default null
, logprobs boolean default null
, top_logprobs int default null
, max_tokens int default null
, max_completion_tokens int default null
, n int default null
, presence_penalty float8 default null
, response_format jsonb default null
, seed int default null
, stop text default null
, temperature float8 default null
, top_p float8 default null
, tools jsonb default null
, tool_choice text default null
, openai_user text default null
, extra_headers jsonb default null
, extra_query jsonb default null
, extra_body jsonb default null
, verbose boolean default false
, client_config jsonb default null
) returns jsonb
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.openai
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.openai.DEFAULT_KEY_NAME, SD)
    client = ai.openai.make_client(plpy, api_key_resolved, ai.openai.str_arg_to_dict(client_config))
    import json

    messages_1 = json.loads(messages)
    if not isinstance(messages_1, list):
      plpy.error("messages is not an array")

    kwargs = ai.openai.create_kwargs(
        frequency_penalty=frequency_penalty,
        logit_bias=ai.openai.str_arg_to_dict(logit_bias),
        logprobs=logprobs,
        top_logprobs=top_logprobs,
        max_tokens=max_tokens,
        max_completion_tokens=max_completion_tokens,
        n=n,
        presence_penalty=presence_penalty,
        response_format=ai.openai.str_arg_to_dict(response_format),
        seed=seed,
        stop=stop,
        temperature=temperature,
        top_p=top_p,
        tools=ai.openai.str_arg_to_dict(tools),
        tool_choice=tool_choice if tool_choice in {'auto', 'none', 'required'} else ai.openai.str_arg_to_dict(tool_choice),
        user=openai_user,
        extra_headers=ai.openai.str_arg_to_dict(extra_headers),
        extra_query=ai.openai.str_arg_to_dict(extra_query),
        extra_body=ai.openai.str_arg_to_dict(extra_body))

    with ai.utils.VerboseRequestTrace(plpy, "openai.chat_complete()", verbose):
        response = client.chat.completions.with_raw_response.create(
            model=model,
            messages=messages_1,
            stream=False,
            **kwargs)

    return response.text
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

------------------------------------------------------------------------------------
-- openai_chat_complete_simple
-- simple chat completion that only requires a message and only returns the response
create or replace function ai.openai_chat_complete_simple
( message text
, api_key text default null
, api_key_name text default null
, verbose boolean default false
, client_config jsonb default null
) returns text
as $$
declare
    model text := 'gpt-4o';
    messages jsonb;
begin
    messages := pg_catalog.jsonb_build_array(
        pg_catalog.jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant'),
        pg_catalog.jsonb_build_object('role', 'user', 'content', message)
    );
    return ai.openai_chat_complete(model, messages, api_key, api_key_name, verbose=>"verbose")
        operator(pg_catalog.->)'choices'
        operator(pg_catalog.->)0
        operator(pg_catalog.->)'message'
        operator(pg_catalog.->>)'content';
end;
$$ language plpgsql volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_moderate
-- classify text as potentially harmful or not
-- https://platform.openai.com/docs/api-reference/moderations/create
create or replace function ai.openai_moderate
( model text
, input_text text
, api_key text default null
, api_key_name text default null
, extra_headers jsonb default null
, extra_query jsonb default null
, extra_body jsonb default null
, verbose boolean default false
, client_config jsonb default null
) returns jsonb
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.openai
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.openai.DEFAULT_KEY_NAME, SD)
    client = ai.openai.make_client(plpy, api_key_resolved, ai.openai.str_arg_to_dict(client_config))
    kwargs = ai.openai.create_kwargs(
        extra_headers=ai.openai.str_arg_to_dict(extra_headers),
        extra_query=ai.openai.str_arg_to_dict(extra_query),
        extra_body=ai.openai.str_arg_to_dict(extra_body))
    with ai.utils.VerboseRequestTrace(plpy, "openai.moderations.create()", verbose):
        moderation = client.moderations.create(
            input=input_text,
            model=model,
            **kwargs)
    return moderation.model_dump_json()
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- openai_moderate_with_raw_response
-- classify text as potentially harmful or not
-- https://platform.openai.com/docs/api-reference/moderations/create
create or replace function ai.openai_moderate_with_raw_response
( model text
, input_text text
, api_key text default null
, api_key_name text default null
, extra_headers jsonb default null
, extra_query jsonb default null
, extra_body jsonb default null
, verbose boolean default false
, client_config jsonb default null
) returns jsonb
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.openai
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.openai.DEFAULT_KEY_NAME, SD)
    client = ai.openai.make_client(plpy, api_key_resolved, ai.openai.str_arg_to_dict(client_config))
    kwargs = ai.openai.create_kwargs(
        extra_headers=ai.openai.str_arg_to_dict(extra_headers),
        extra_query=ai.openai.str_arg_to_dict(extra_query),
        extra_body=ai.openai.str_arg_to_dict(extra_body))
    with ai.utils.VerboseRequestTrace(plpy, "openai.moderations.create()", verbose):
        moderation = client.moderations.with_raw_response.create(
            input=input_text,
            model=model,
            **kwargs)
    return moderation.text
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;


-------------------------------------------------------------------------------
-- openai_client_config
-- Generate a JSON object with the configuration for the OpenAI client.
create or replace function ai.openai_client_config
( base_url text default null
, timeout_seconds float8 default null
, organization text default null
, project text default null
, max_retries int default null
, default_headers jsonb default null
, default_query jsonb default null
) returns jsonb
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.openai
    import ai.secrets
    import json

    client_config = ai.openai.create_kwargs(
        base_url=base_url,
        timeout=timeout_seconds,
        organization=organization,
        project=project,
        max_retries=max_retries,
        default_headers=ai.openai.str_arg_to_dict(default_headers),
        default_query=ai.openai.str_arg_to_dict(default_query),
    )
    return json.dumps(client_config)
$python$
  language plpython3u immutable security invoker
  set search_path to pg_catalog, pg_temp
;


--------------------------------------------------------------------------------
-- 002-ollama.sql

-------------------------------------------------------------------------------
-- ollama_list_models
-- https://github.com/ollama/ollama/blob/main/docs/api.md#list-local-models
--
create or replace function ai.ollama_list_models(host text default null, verbose boolean default false)
returns table
( "name" text
, model text
, size bigint
, digest text
, family text
, format text
, families jsonb
, parent_model text
, parameter_size text
, quantization_level text
, modified_at timestamptz
)
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.ollama
    import ai.utils
    client = ai.ollama.make_client(plpy, host)
    import json
    with ai.utils.VerboseRequestTrace(plpy, "ollama.list()", verbose):
        resp = client.list()
    models = resp.get("models")
    if models is None:
        raise StopIteration
    for m in models:
        d = m.get("details")
        yield ( m.get("name")
            , m.get("model")
            , m.get("size")
            , m.get("digest")
            , d.get("family") if d is not None else None
            , d.get("format") if d is not None else None
            , json.dumps(d.get("families")) if d is not None else None
            , d.get("parent_model") if d is not None else None
            , d.get("parameter_size") if d is not None else None
            , d.get("quantization_level") if d is not None else None
            , m.get("modified_at")
        )
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- ollama_ps
-- https://github.com/ollama/ollama/blob/main/docs/api.md#list-running-models
create or replace function ai.ollama_ps(host text default null, verbose boolean default false)
returns table
( "name" text
, model text
, size bigint
, digest text
, parent_model text
, format text
, family text
, families jsonb
, parameter_size text
, quantization_level text
, expires_at timestamptz
, size_vram bigint
)
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.ollama
    import ai.utils
    client = ai.ollama.make_client(plpy, host)
    import json
    with ai.utils.VerboseRequestTrace(plpy, "ollama.ps()", verbose):
        resp = client.ps()
    models = resp.get("models")
    if models is None:
        raise StopIteration
    for m in models:
        d = m.get("details")
        yield ( m.get("name")
            , m.get("model")
            , m.get("size")
            , m.get("digest")
            , d.get("parent_model") if d is not None else None
            , d.get("format") if d is not None else None
            , d.get("family") if d is not None else None
            , json.dumps(d.get("families")) if d is not None else None
            , d.get("parameter_size") if d is not None else None
            , d.get("quantization_level") if d is not None else None
            , m.get("expires_at")
            , m.get("size_vram")
        )
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- ollama_embed
-- https://github.com/ollama/ollama/blob/main/docs/api.md#generate-embeddings
create or replace function ai.ollama_embed
( model text
, input_text text
, host text default null
, keep_alive text default null
, embedding_options jsonb default null
, verbose boolean default false
) returns @extschema:vector@.vector
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.ollama
    import ai.utils
    client = ai.ollama.make_client(plpy, host)
    embedding_options_1 = None
    if embedding_options is not None:
        import json
        embedding_options_1 = {k: v for k, v in json.loads(embedding_options).items()}
    with ai.utils.VerboseRequestTrace(plpy, "ollama.embeddings()", verbose):
        resp = client.embeddings(model, input_text, options=embedding_options_1, keep_alive=keep_alive)
    return resp.get("embedding")
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- ollama_generate
-- https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-completion
create or replace function ai.ollama_generate
( model text
, prompt text
, host text default null
, images bytea[] default null
, keep_alive text default null
, embedding_options jsonb default null
, system_prompt text default null
, template text default null
, context int[] default null
, verbose boolean default false
) returns jsonb
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.ollama
    import ai.utils
    client = ai.ollama.make_client(plpy, host)

    import json
    args = {}

    if keep_alive is not None:
        args["keep_alive"] = keep_alive

    if embedding_options is not None:
        args["options"] = {k: v for k, v in json.loads(embedding_options).items()}

    if system_prompt is not None:
        args["system"] = system_prompt

    if template is not None:
        args["template"] = template

    if context is not None:
        args["context"] = context

    if images is not None:
        import base64
        images_1 = []
        for image in images:
            images_1.append(base64.b64encode(image).decode('utf-8'))
        args["images"] = images_1

    with ai.utils.VerboseRequestTrace(plpy, "ollama.generate()", verbose):
        resp = client.generate(model, prompt, stream=False, **args)
    return resp.model_dump_json()
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- ollama_chat_complete
-- https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-chat-completion
create or replace function ai.ollama_chat_complete
( model text
, messages jsonb
, host text default null
, keep_alive text default null
, chat_options jsonb default null
, tools jsonb default null
, response_format jsonb default null
, verbose boolean default false
) returns jsonb
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import json
    import ai.ollama
    import ai.utils
    client = ai.ollama.make_client(plpy, host)

    import json
    import base64
    args = {}

    if keep_alive is not None:
        args["keep_alive"] = keep_alive

    if chat_options is not None:
        args["options"] = {k: v for k, v in json.loads(chat_options).items()}

    if tools is not None:
        args["tools"] = json.loads(tools)

    if response_format is not None:
        args["format"] = json.loads(response_format)

    messages_1 = json.loads(messages)
    if not isinstance(messages_1, list):
        plpy.error("messages is not an array")

    # the python api expects bytes objects for images
    # decode the base64 encoded images into raw binary
    for message in messages_1:
        if 'images' in message:
            decoded = [base64.b64decode(image) for image in message["images"]]
            message["images"] = decoded

    with ai.utils.VerboseRequestTrace(plpy, "ollama.chat()", verbose):
        resp = client.chat(model, messages_1, stream=False, **args)

    return resp.model_dump_json()
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;


--------------------------------------------------------------------------------
-- 003-anthropic.sql
-------------------------------------------------------------------------------
-- anthropic_list_models
-- https://docs.anthropic.com/en/api/models-list
create or replace function ai.anthropic_list_models(api_key text default null, api_key_name text default null, base_url text default null, verbose boolean default false)
returns table
( id text
, name text
, created timestamptz
)
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.anthropic
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.anthropic.DEFAULT_KEY_NAME, SD)
    
    with ai.utils.VerboseRequestTrace(plpy, "anthropic.list_models()", verbose):
        result = ai.anthropic.list_models(api_key_resolved, base_url)
    
    for tup in result:
        yield tup
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- anthropic_generate
-- https://docs.anthropic.com/en/api/messages
create or replace function ai.anthropic_generate
( model text
, messages jsonb
, max_tokens int default 1024
, api_key text default null
, api_key_name text default null
, base_url text default null
, timeout float8 default null
, max_retries int default null
, system_prompt text default null
, user_id text default null
, stop_sequences text[] default null
, temperature float8 default null
, tool_choice jsonb default null
, tools jsonb default null
, top_k int default null
, top_p float8 default null
, verbose boolean default false
) returns jsonb
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.anthropic
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.anthropic.DEFAULT_KEY_NAME, SD)
    client = ai.anthropic.make_client(api_key=api_key_resolved, base_url=base_url, timeout=timeout, max_retries=max_retries)

    import json
    messages_1 = json.loads(messages)

    args = {}
    if system_prompt is not None:
        args["system"] = system_prompt
    if user_id is not None:
        args["metadata"] = {"user_id", user_id}
    if stop_sequences is not None:
        args["stop_sequences"] = stop_sequences
    if temperature is not None:
        args["temperature"] = temperature
    if tool_choice is not None:
        args["tool_choice"] = json.loads(tool_choice)
    if tools is not None:
        args["tools"] = json.loads(tools)
    if top_k is not None:
        args["top_k"] = top_k
    if top_p is not None:
        args["top_p"] = top_p

    with ai.utils.VerboseRequestTrace(plpy, "anthropic.generate()", verbose):
        message = client.messages.create(model=model, messages=messages_1, max_tokens=max_tokens, **args)
    
    return message.to_json()
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

--------------------------------------------------------------------------------
-- 004-cohere.sql
-------------------------------------------------------------------------------
-- cohere_list_models
-- https://docs.cohere.com/reference/list-models
create or replace function ai.cohere_list_models
( api_key text default null
, api_key_name text default null
, endpoint text default null
, default_only bool default null
, verbose boolean default false
)
returns table
( "name" text
, endpoints text[]
, finetuned bool
, context_length int
, tokenizer_url text
, default_endpoints text[]
)
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.cohere
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    args = {}
    if endpoint is not None:
        args["endpoint"] = endpoint
    if default_only is not None:
        args["default_only"] = default_only
    page_token = None
    while True:
        with ai.utils.VerboseRequestTrace(plpy, "cohere.list_models()", verbose):
            resp = client.models.list(page_size=1000, page_token=page_token, **args)
        for model in resp.models:
            yield (model.name, model.endpoints, model.finetuned, model.context_length, model.tokenizer_url, model.default_endpoints)
        page_token = resp.next_page_token
        if page_token is None:
            break
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_tokenize
-- https://docs.cohere.com/reference/tokenize
create or replace function ai.cohere_tokenize(model text, text_input text, api_key text default null, api_key_name text default null, verbose boolean default false) returns int[]
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.cohere
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    with ai.utils.VerboseRequestTrace(plpy, "cohere.tokenize()", verbose):
        response = client.tokenize(text=text_input, model=model)
    return response.tokens
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_detokenize
-- https://docs.cohere.com/reference/detokenize
create or replace function ai.cohere_detokenize(model text, tokens int[], api_key text default null, api_key_name text default null, verbose boolean default false) returns text
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.cohere
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    with ai.utils.VerboseRequestTrace(plpy, "cohere.detokenize()", verbose):
        response = client.detokenize(tokens=tokens, model=model)
    return response.text
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_embed
-- https://docs.cohere.com/reference/embed-1
create or replace function ai.cohere_embed
( model text
, input_text text
, api_key text default null
, api_key_name text default null
, input_type text default null
, truncate_long_inputs text default null
, verbose boolean default false
) returns @extschema:vector@.vector
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.cohere
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    args={}
    if input_type is not None:
        args["input_type"] = input_type
    if truncate_long_inputs is not None:
        args["truncate"] = truncate_long_inputs
    with ai.utils.VerboseRequestTrace(plpy, "cohere.embed()", verbose):
        response = client.embed(texts=[input_text], model=model, embedding_types=["float"], **args)
    return response.embeddings.float[0]
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_classify
-- https://docs.cohere.com/reference/classify
create or replace function ai.cohere_classify
( model text
, inputs text[]
, api_key text default null
, api_key_name text default null
, examples jsonb default null
, truncate_long_inputs text default null
, verbose boolean default false
) returns jsonb
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.cohere
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    import json
    args = {}
    if examples is not None:
        args["examples"] = json.loads(examples)
    if truncate_long_inputs is not None:
        args["truncate"] = truncate_long_inputs

    with ai.utils.VerboseRequestTrace(plpy, "cohere.classify()", verbose):
        response = client.classify(inputs=inputs, model=model, **args)
    return response.json()
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_classify_simple
-- https://docs.cohere.com/reference/classify
create or replace function ai.cohere_classify_simple
( model text
, inputs text[]
, api_key text default null
, api_key_name text default null
, examples jsonb default null
, truncate_long_inputs text default null
, verbose boolean default false
) returns table
( input text
, prediction text
, confidence float8
)
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.cohere
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    import json
    args = {}
    if examples is not None:
        args["examples"] = json.loads(examples)
    if truncate_long_inputs is not None:
        args["truncate"] = truncate_long_inputs
    
    with ai.utils.VerboseRequestTrace(plpy, "cohere.classify()", verbose):
        response = client.classify(inputs=inputs, model=model, **args)
    for x in response.classifications:
        yield x.input, x.prediction, x.confidence
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_rerank
-- https://docs.cohere.com/reference/rerank
create or replace function ai.cohere_rerank
( model text
, query text
, documents text[]
, api_key text default null
, api_key_name text default null
, top_n integer default null
, max_tokens_per_doc int default null
, verbose boolean default false
) returns jsonb
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.cohere
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    args = {}
    if top_n is not None:
        args["top_n"] = top_n
    if max_tokens_per_doc is not None:
        args["max_tokens_per_doc"] = max_tokens_per_doc
    with ai.utils.VerboseRequestTrace(plpy, "cohere.rerank()", verbose):
        response = client.rerank(model=model, query=query, documents=documents, **args)
    return response.json()
$python$ language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_rerank_simple
-- https://docs.cohere.com/reference/rerank
create or replace function ai.cohere_rerank_simple
( model text
, query text
, documents text[]
, api_key text default null
, api_key_name text default null
, top_n integer default null
, max_tokens_per_doc int default null
, verbose boolean default false
) returns table
( "index" int
, "document" text
, relevance_score float8
)
as $func$
select
  x."index"
, d.document
, x.relevance_score
from pg_catalog.jsonb_to_recordset
(
    ai.cohere_rerank
    ( model
    , query
    , documents
    , api_key=>api_key
    , api_key_name=>api_key_name
    , top_n=>top_n
    , max_tokens_per_doc=>max_tokens_per_doc
    , verbose=>"verbose"
    ) operator(pg_catalog.->) 'results'
) x("index" int, relevance_score float8)
inner join unnest(documents) with ordinality d (document, ord)
on (x."index" = (d.ord - 1))
$func$ language sql immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- cohere_chat_complete
-- https://docs.cohere.com/reference/chat
create or replace function ai.cohere_chat_complete
( model text
, messages jsonb
, api_key text default null
, api_key_name text default null
, tools jsonb default null
, documents jsonb default null
, citation_options jsonb default null
, response_format jsonb default null
, safety_mode text default null
, max_tokens int default null
, stop_sequences text[] default null
, temperature float8 default null
, seed int default null
, frequency_penalty float8 default null
, presence_penalty float8 default null
, k int default null
, p float8 default null
, logprobs boolean default null
, tool_choice text default null
, strict_tools bool default null
, verbose boolean default false
) returns jsonb
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.cohere
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.cohere.DEFAULT_KEY_NAME, SD)
    client = ai.cohere.make_client(api_key_resolved)

    import json
    args = {}

    if tools is not None:
        args["tools"] = json.loads(tools)
    if documents is not None:
        args["documents"] = json.loads(documents)
    if citation_options is not None:
        args["citation_options"] = json.loads(citation_options)
    if response_format is not None:
        args["response_format"] = json.loads(response_format)
    if safety_mode is not None:
        args["safety_mode"] = safety_mode
    if max_tokens is not None:
        args["max_tokens"] = max_tokens
    if stop_sequences is not None:
        args["stop_sequences"] = stop_sequences
    if temperature is not None:
        args["temperature"] = temperature
    if seed is not None:
        args["seed"] = seed
    if frequency_penalty is not None:
        args["frequency_penalty"] = frequency_penalty
    if presence_penalty is not None:
        args["presence_penalty"] = presence_penalty
    if k is not None:
        args["k"] = k
    if p is not None:
        args["p"] = p
    if logprobs is not None:
        args["logprobs"] = logprobs
    if tool_choice is not None:
        args["tool_choice"] = tool_choice
    if strict_tools is not None:
        args["strict_tools"] = strict_tools

    with ai.utils.VerboseRequestTrace(plpy, "cohere.chat_complete()", verbose):
        response = client.chat(model=model, messages=json.loads(messages), **args)
    return response.json()
$python$ language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

--------------------------------------------------------------------------------
-- 015-vectorizer-api.sql


-------------------------------------------------------------------------------
-- execute_vectorizer
create or replace function ai.execute_vectorizer(vectorizer_id pg_catalog.int4) returns void
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.vectorizer
    ai.vectorizer.execute_vectorizer(plpy, vectorizer_id)
$python$
language plpython3u volatile security invoker
set search_path to pg_catalog, pg_temp
;

--------------------------------------------------------------------------------
-- 016-secrets.sql
-------------------------------------------------------------------------------
-- reveal_secret
create or replace function ai.reveal_secret
( secret_name pg_catalog.text
, use_cache pg_catalog.bool default true
) returns pg_catalog.text
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.secrets
    if use_cache:
        return ai.secrets.reveal_secret(plpy, secret_name, SD)
    else:
        ai.secrets.remove_secret_from_cache(SD, secret_name)
        return ai.secrets.reveal_secret(plpy, secret_name, None)
$python$
language plpython3u stable security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- secret_permissions
create or replace view ai.secret_permissions as
select *
from ai._secret_permissions
where pg_catalog.to_regrole("role") is not null
      and pg_catalog.pg_has_role(current_user, "role", 'member');

-------------------------------------------------------------------------------
-- grant_secret
create or replace function ai.grant_secret
( secret_name pg_catalog.text
, grant_to_role pg_catalog.text
) returns void
as $func$
    insert into ai._secret_permissions ("name", "role") values (secret_name, grant_to_role);
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp;

-------------------------------------------------------------------------------
-- revoke_secret
create or replace function ai.revoke_secret
( secret_name pg_catalog.text
, revoke_from_role pg_catalog.text
) returns void
as $func$
    delete from ai._secret_permissions
    where "name" operator(pg_catalog.=) secret_name
    and "role" operator(pg_catalog.=) revoke_from_role;
$func$ language sql volatile security invoker
set search_path to pg_catalog, pg_temp;


--------------------------------------------------------------------------------
-- 017-voyageai.sql
-------------------------------------------------------------------------------
-- voyageai_embed
-- generate an embedding from a text value
-- https://docs.voyageai.com/reference/embeddings-api
create or replace function ai.voyageai_embed
( model text
, input_text text
, input_type text default null
, api_key text default null
, api_key_name text default null
, verbose boolean default false
) returns @extschema:vector@.vector
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.voyageai
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.voyageai.DEFAULT_KEY_NAME, SD)
    with ai.utils.VerboseRequestTrace(plpy, "voyageai.embed()", verbose):
        args = {}
        if input_type is not None:
            args["input_type"] = input_type
    for tup in ai.voyageai.embed(model, [input_text], api_key=api_key_resolved, **args):
        return tup[1]
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- voyageai_embed
-- generate embeddings from an array of text values
-- https://docs.voyageai.com/reference/embeddings-api
create or replace function ai.voyageai_embed
( model text
, input_texts text[]
, input_type text default null
, api_key text default null
, api_key_name text default null
, verbose boolean default false
) returns table
( "index" int
, embedding @extschema:vector@.vector
)
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.voyageai
    import ai.secrets
    import ai.utils
    api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, ai.voyageai.DEFAULT_KEY_NAME, SD)
    args = {}
    if input_type is not None:
        args["input_type"] = input_type
    
    with ai.utils.VerboseRequestTrace(plpy, "voyageai.embed()", verbose):
        results = ai.voyageai.embed(model, input_texts, api_key=api_key_resolved, **args) 
        
    for tup in results:
        yield tup
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;


--------------------------------------------------------------------------------
-- 018-load_dataset.sql
create or replace procedure ai.load_dataset_multi_txn
( name text
, config_name text default null
, split text default null
, schema_name name default 'public'
, table_name name default null
, if_table_exists text default 'error'
, field_types jsonb default null
, batch_size int default 5000
, max_batches int default null
, commit_every_n_batches int default 1
, kwargs jsonb default '{}'
)
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.load_dataset
    import json
     
    # Convert kwargs from json string to dict
    kwargs_dict = {}
    if kwargs:
        kwargs_dict = json.loads(kwargs)
    
    # Convert field_types from json string to dict
    field_types_dict = None 
    if field_types:
        field_types_dict = json.loads(field_types)
    
    
    num_rows = ai.load_dataset.load_dataset(
        plpy,
        name=name,
        config_name=config_name,
        split=split,
        schema=schema_name,
        table_name=table_name,
        if_table_exists=if_table_exists,
        field_types=field_types_dict,
        batch_size=batch_size,
        max_batches=max_batches,
        commit_every_n_batches=commit_every_n_batches,
        **kwargs_dict
    )
$python$
language plpython3u security invoker;

create or replace function ai.load_dataset
( name text
, config_name text default null
, split text default null
, schema_name name default 'public'
, table_name name default null
, if_table_exists text default 'error'
, field_types jsonb default null
, batch_size int default 5000
, max_batches int default null
, kwargs jsonb default '{}'
) returns bigint
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.load_dataset
    import json
    
    # Convert kwargs from json string to dict
    kwargs_dict = {}
    if kwargs:
        kwargs_dict = json.loads(kwargs)
    
    # Convert field_types from json string to dict
    field_types_dict = None 
    if field_types:
        field_types_dict = json.loads(field_types)
    
    return ai.load_dataset.load_dataset(
        plpy,
        name=name,
        config_name=config_name,
        split=split,
        schema=schema_name,
        table_name=table_name,
        if_table_exists=if_table_exists,
        field_types=field_types_dict,
        batch_size=batch_size,
        max_batches=max_batches,
        commit_every_n_batches=None,
        **kwargs_dict
    )
$python$
language plpython3u volatile security invoker
set search_path to pg_catalog, pg_temp;

--------------------------------------------------------------------------------
-- 019-litellm.sql
-------------------------------------------------------------------------------
-- litellm_embed
-- generate an embedding from a text value
create or replace function ai.litellm_embed
( model text
, input_text text
, api_key text default null
, api_key_name text default null
, extra_options jsonb default null
, verbose boolean default false
) returns @extschema:vector@.vector
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.litellm
    import ai.secrets
    options = {}
    if extra_options is not None:
        import json
        options = {k: v for k, v in json.loads(extra_options).items()}

    if api_key is not None or api_key_name is not None:
        api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, "", SD)
    else:
        api_key_resolved = None
    
    with ai.utils.VerboseRequestTrace(plpy, "litellm.embed()", verbose):
        result = ai.litellm.embed(model, [input_text], api_key=api_key_resolved, **options)
    
    for tup in result:
        return tup[1]
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- litellm_embed
-- generate embeddings from an array of text values
create or replace function ai.litellm_embed
( model text
, input_texts text[]
, api_key text default null
, api_key_name text default null
, extra_options jsonb default null
, verbose boolean default false
) returns table
( "index" int
, embedding @extschema:vector@.vector
)
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    import ai.litellm
    import ai.secrets
    options = {}
    if extra_options is not None:
        import json
        options = {k: v for k, v in json.loads(extra_options).items()}

    if api_key is not None or api_key_name is not None:
        api_key_resolved = ai.secrets.get_secret(plpy, api_key, api_key_name, "", SD)
    else:
        api_key_resolved = None
    
    with ai.utils.VerboseRequestTrace(plpy, "litellm.embed()", verbose):
        result = ai.litellm.embed(model, input_texts, api_key=api_key_resolved, **options)
    
    for tup in result:
        yield tup
$python$
language plpython3u immutable parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

--------------------------------------------------------------------------------
-- 020-chunk.sql

-------------------------------------------------------------------------------
-- chunk_text
create or replace function ai.chunk_text
( input text
, chunk_size int default null
, chunk_overlap int default null
, separator text default null
, is_separator_regex bool default false
) returns table
( seq bigint
, chunk text
)
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    from langchain_text_splitters import CharacterTextSplitter
    
    args = {}
    if separator is not None:
        args["separator"] = separator
    if chunk_size is not None:
        args["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        args["chunk_overlap"] = chunk_overlap
    if is_separator_regex is not None:
        args["is_separator_regex"] = is_separator_regex
    
    chunker = CharacterTextSplitter(**args)
    for ix, chunk in enumerate(chunker.split_text(input)):
        yield ix, chunk
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- chunk_text_recursively
create or replace function ai.chunk_text_recursively
( input text
, chunk_size int default null
, chunk_overlap int default null
, separators text[] default null
, is_separator_regex bool default false
) returns table
( seq bigint
, chunk text
)
as $python$
    if "ai.version" not in GD:
        r = plpy.execute("select coalesce(pg_catalog.current_setting('ai.python_lib_dir', true), '/usr/local/lib/pgai') as python_lib_dir")
        python_lib_dir = r[0]["python_lib_dir"]
        from pathlib import Path
        import sys
        import sysconfig
        # Note: we remove system-level python packages from the path to avoid
        # them being loaded and taking precedence over our dependencies.
        # This seems paranoid, but it was a real problem.
        if "purelib" in sysconfig.get_path_names() and sysconfig.get_path("purelib") in sys.path:
            sys.path.remove(sysconfig.get_path("purelib"))
        python_lib_dir = Path(python_lib_dir).joinpath("0.10.1")
        import site
        site.addsitedir(str(python_lib_dir))
        from ai import __version__ as ai_version
        assert("0.10.1" == ai_version)
        GD["ai.version"] = "0.10.1"
    else:
        if GD["ai.version"] != "0.10.1":
            plpy.fatal("the pgai extension version has changed. start a new session")
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    args = {}
    if separators is not None:
        args["separators"] = separators
    if chunk_size is not None:
        args["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        args["chunk_overlap"] = chunk_overlap
    if is_separator_regex is not None:
        args["is_separator_regex"] = is_separator_regex
    
    chunker = RecursiveCharacterTextSplitter(**args)
    for ix, chunk in enumerate(chunker.split_text(input)):
        yield ix, chunk
$python$
language plpython3u volatile parallel safe security invoker
set search_path to pg_catalog, pg_temp
;


--------------------------------------------------------------------------------
-- 999-privileges.sql

-------------------------------------------------------------------------------
-- grant_ai_usage
create or replace function ai.grant_ai_usage(to_user pg_catalog.name, admin pg_catalog.bool default false) returns void
as $func$
declare
    _sql pg_catalog.text;
begin
    -- schema
    select pg_catalog.format
    ( 'grant %s on schema ai to %I%s'
    , case when admin then 'all privileges' else 'usage, create' end
    , to_user
    , case when admin then ' with grant option' else '' end
    ) into strict _sql
    ;
    raise debug '%', _sql;
    execute _sql;

    -- tables, sequences, and views
    for _sql in
    (
        select pg_catalog.format
        ( 'grant %s on %s %I.%I to %I%s'
        , case
            when admin then 'all privileges'
            else
                case
                    when k.relname operator(pg_catalog.=) 'semantic_catalog' then 'select'
                    when k.relkind in ('r', 'p') then 'select, insert, update, delete'
                    when k.relkind in ('S') then 'usage, select, update'
                    when k.relkind in ('v') then 'select'
                end
          end
        , case
            when k.relkind in ('r', 'p') then 'table'
            when k.relkind in ('S') then 'sequence'
            when k.relkind in ('v') then ''
          end
        , n.nspname
        , k.relname
        , to_user
        , case when admin then ' with grant option' else '' end
        )
        from pg_catalog.pg_depend d
        inner join pg_catalog.pg_extension e on (d.refobjid operator(pg_catalog.=) e.oid)
        inner join pg_catalog.pg_class k on (d.objid operator(pg_catalog.=) k.oid)
        inner join pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
        where d.refclassid operator(pg_catalog.=) 'pg_catalog.pg_extension'::pg_catalog.regclass
        and d.deptype operator(pg_catalog.=) 'e'
        and e.extname operator(pg_catalog.=) 'ai'
        and k.relkind in ('r', 'p', 'S', 'v') -- tables, sequences, and views
        and (admin, n.nspname, k.relname) not in
        ( (false, 'ai', 'migration') -- only admins get any access to this table
        , (false, 'ai', '_secret_permissions') -- only admins get any access to this table
        , (false, 'ai', 'feature_flag') -- only admins get any access to this table
        )
        order by n.nspname, k.relname
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;

    -- procedures and functions
    for _sql in
    (
        select pg_catalog.format
        ( 'grant %s on %s %I.%I(%s) to %I%s'
        , case when admin then 'all privileges' else 'execute' end
        , case k.prokind
              when 'f' then 'function'
              when 'p' then 'procedure'
          end
        , n.nspname
        , k.proname
        , pg_catalog.pg_get_function_identity_arguments(k.oid)
        , to_user
        , case when admin then ' with grant option' else '' end
        )
        from pg_catalog.pg_depend d
        inner join pg_catalog.pg_extension e on (d.refobjid operator(pg_catalog.=) e.oid)
        inner join pg_catalog.pg_proc k on (d.objid operator(pg_catalog.=) k.oid)
        inner join pg_namespace n on (k.pronamespace operator(pg_catalog.=) n.oid)
        where d.refclassid operator(pg_catalog.=) 'pg_catalog.pg_extension'::pg_catalog.regclass
        and d.deptype operator(pg_catalog.=) 'e'
        and e.extname operator(pg_catalog.=) 'ai'
        and k.prokind in ('f', 'p')
        and case
              when k.proname in
                ( 'grant_ai_usage'
                , 'grant_secret'
                , 'revoke_secret'
                , 'post_restore'
                , 'create_semantic_catalog'
                )
              then admin -- only admins get these function
              else true
            end
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;
    
    -- secret permissions
    if admin then
        -- grant access to all secrets to admin users
        insert into ai._secret_permissions ("name", "role")
        values ('*', to_user)
        on conflict on constraint _secret_permissions_pkey
        do nothing
        ;
    end if;
end
$func$ language plpgsql volatile
security invoker -- gotta have privs to give privs
set search_path to pg_catalog, pg_temp
;

-------------------------------------------------------------------------------
-- grant admin usage to session user and pg_database_owner
select ai.grant_ai_usage(pg_catalog."session_user"(), admin=>true);
select ai.grant_ai_usage('pg_database_owner', admin=>true);

-------------------------------------------------------------------------------
-- revoke everything from public
do language plpgsql $func$
declare
    _sql text;
begin
    -- schema
    revoke all privileges on schema ai from public;

    -- tables, sequences, and views
    for _sql in
    (
        select pg_catalog.format
        ( 'revoke all privileges on %s %I.%I from public'
        , case
            when k.relkind in ('r', 'p') then 'table'
            when k.relkind in ('S') then 'sequence'
            when k.relkind in ('v') then ''
          end
        , n.nspname
        , k.relname
        )
        from pg_catalog.pg_depend d
        inner join pg_catalog.pg_extension e on (d.refobjid operator(pg_catalog.=) e.oid)
        inner join pg_catalog.pg_class k on (d.objid operator(pg_catalog.=) k.oid)
        inner join pg_namespace n on (k.relnamespace operator(pg_catalog.=) n.oid)
        where d.refclassid operator(pg_catalog.=) 'pg_catalog.pg_extension'::pg_catalog.regclass
        and d.deptype operator(pg_catalog.=) 'e'
        and e.extname operator(pg_catalog.=) 'ai'
        and k.relkind in ('r', 'p', 'S', 'v') -- tables, sequences, and views
        order by n.nspname, k.relname
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;

    -- procedures and functions
    for _sql in
    (
        select pg_catalog.format
        ( 'revoke all privileges on %s %I.%I(%s) from public'
        , case k.prokind
              when 'f' then 'function'
              when 'p' then 'procedure'
          end
        , n.nspname
        , k.proname
        , pg_catalog.pg_get_function_identity_arguments(k.oid)
        )
        from pg_catalog.pg_depend d
        inner join pg_catalog.pg_extension e on (d.refobjid operator(pg_catalog.=) e.oid)
        inner join pg_catalog.pg_proc k on (d.objid operator(pg_catalog.=) k.oid)
        inner join pg_namespace n on (k.pronamespace operator(pg_catalog.=) n.oid)
        where d.refclassid operator(pg_catalog.=) 'pg_catalog.pg_extension'::pg_catalog.regclass
        and d.deptype operator(pg_catalog.=) 'e'
        and e.extname operator(pg_catalog.=) 'ai'
        and k.prokind in ('f', 'p')
    )
    loop
        raise debug '%', _sql;
        execute _sql;
    end loop;
end
$func$;


