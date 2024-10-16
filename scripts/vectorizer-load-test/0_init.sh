#!/usr/bin/env bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install python-dotenv datasets "psycopg[binary]"