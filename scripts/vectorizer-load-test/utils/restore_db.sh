#!/usr/bin/env bash
set -e
if [ -f .env ]; then 
    set -a 
    source .env
    set +a
fi
pg_restore -d "$DB_URL" -v -Fc --exit-on-error --no-owner --no-privileges wiki.dump
