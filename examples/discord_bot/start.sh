#!/bin/bash

# Exit on any error
set -e
export PYTHONPATH="/app:${PYTHONPATH}"
echo "Running database migrations..."
uv run alembic upgrade head

echo "Inserting documentation into database..."
uv run python pgai_discord_bot/insert_docs.py

echo "Starting Discord bot..."
uv run python pgai_discord_bot/main.py