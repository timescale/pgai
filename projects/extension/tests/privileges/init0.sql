
-- psql var for users
\set users {bob,fred,alice,jill}

drop database if exists privs with (force);

-- (re)create some test users
select
  format('drop user if exists %I', u, u)
, format('create user %I', u, u)
from unnest(:'users'::text[]) u
\gexec

grant alice to current_user;
create database privs owner alice;


