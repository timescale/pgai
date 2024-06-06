#!/usr/bin/env bash
# this should be run from INSIDE the docker container / virtual machine
set -e
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY is not set or is empty."
    exit 1
fi
# copy the latest sources to the correct postgres dir
make install_extension
# if the "test" database exists, drop it
psql -d postgres -f - <<EOF
select count(*) > 0 as test_db_exists
from pg_database where datname = 'test'
\gset
\if :test_db_exists
drop database test;
\endif
EOF
# create a fresh "test" database
psql -d postgres -c "create database test;"
# run the tests in the test database
psql -d test -f tests.sql
