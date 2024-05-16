#!/usr/bin/env bash
set -e
sudo cp /pgai/pgai.control /usr/share/postgresql/16/extension
sudo cp /pgai/pgai--1.0.sql /usr/share/postgresql/16/extension
psql --echo-errors --echo-queries -v VERBOSITY=verbose -c "drop extension if exists pgai; create extension pgai cascade;"
