#!/usr/bin/env bash
set -e
sudo cp /pgai/src/* /usr/share/postgresql/16/extension
psql --echo-errors --echo-queries -v VERBOSITY=verbose -f - <<EOF
drop extension if exists ai cascade;
create extension ai cascade;
EOF
