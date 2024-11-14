create table ai._secret_permissions
( name text not null check(name = '*' or name ~ '^[A-Za-z0-9_.]+$')
, "role" text not null
, primary key (name, "role")
);
-- we add a filter to the dump config in 007-secret_permissions-dump-filter.sql
perform pg_catalog.pg_extension_config_dump('ai._secret_permissions'::pg_catalog.regclass, '');
--only admins will have access to this table
revoke all on ai._secret_permissions from public;
