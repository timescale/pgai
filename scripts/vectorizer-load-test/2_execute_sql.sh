#!/usr/bin/env sh
if [ $# -eq 0 ]
  then
    echo "Please provide a path to a .sql file"
    exit 1
fi

envfile_path=.env
if [ "$2" ]
  then
    envfile_path="$2" # If second arg is provided, use it as path of the .env file
fi

if [ ! -f "$envfile_path" ]
  then
    echo "A .env file is required. Please create one or specify the path to the file via second argument"
    exit 1
fi

# shellcheck disable=SC1090
set -a && . "$envfile_path" && set +a # this loads the env vars from the .env file
psql "$DB_URL" -f "$1"