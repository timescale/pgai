create or replace function ai.grant_vectorizer_usage(to_user pg_catalog.name, admin pg_catalog.bool default false) returns void
as $func$
begin
    if not admin then
        execute 'grant usage, create on schema ai to ' || to_user;
        execute 'grant select, insert, update, delete on table ai.vectorizer to ' || to_user;
        execute 'grant select on ai.vectorizer_errors to ' || to_user;
        execute 'grant select on ai.vectorizer_status to ' || to_user;
        execute 'grant select, usage on sequence ai.vectorizer_id_seq to ' || to_user;
    else
        execute 'grant all privileges on schema ai to ' || to_user;
        execute 'grant all privileges on table ai.pgai_lib_migration to ' || to_user;
        execute 'grant all privileges on table ai.pgai_lib_version to ' || to_user;
        execute 'grant all privileges on table ai.pgai_lib_feature_flag to ' || to_user;
        execute 'grant all privileges on table ai.vectorizer to ' || to_user;
        execute 'grant all privileges on table ai.vectorizer_errors to ' || to_user;
        execute 'grant all privileges on table ai.vectorizer_status to ' || to_user;
        execute 'grant all privileges on sequence ai.vectorizer_id_seq to ' || to_user;
    end if;
end
$func$ language plpgsql volatile
security invoker -- gotta have privs to give privs
set search_path to pg_catalog, pg_temp
;