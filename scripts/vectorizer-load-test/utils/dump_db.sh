#!/usr/bin/env bash
set -e
if [ -f .env ]; then 
    set -a 
    source .env
    set +a
fi
pg_dump -d "$DB_URL" -Fc -v -f wiki.dump --no-owner --no-privileges --table=public.wiki
