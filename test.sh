#!/usr/bin/env bash
set -e

# if a .env file exists, load and export the variables in it
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

if [ -n "$WHERE_AM_I" ] && [ "$WHERE_AM_I" == "docker" ]; then
  if [ "$(whoami)" == "root" ]; then
    echo switching to postgres user...
    su postgres -
  fi
  psql -d postgres -f test.sql
else
  psql --no-psqlrc -d 'postgres://postgres@127.0.0.1:9876/postgres' -f test.sql
fi
