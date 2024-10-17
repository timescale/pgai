#!/usr/bin/env bash

if [ -d '.venv' ]; then
    source .venv/bin/activate
else
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install python-dotenv datasets "psycopg[binary]"
fi

python3 load.py
