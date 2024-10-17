#!/usr/bin/env bash

# if you have already generated a wiki.dump file using load.sh
# you can skip load.sh in the future and run this script to restore from the dump

if [ ! -f "wiki.dump" ]; then
  echo "wiki.dump does not exist"
  exit 1
fi

if [ -f '.env' ]; then
  set -a && . ".env" && set +a # this loads the env vars from the .env file
fi
pg_restore -d "$DB_URL" -v -Fc --exit-on-error --no-owner --no-privileges wiki.dump
