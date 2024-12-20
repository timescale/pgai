# Code LLM Sync

This is an example project using pgai in python with FastAPI, SQLAlchemy, alembic and pytest as well as python-pgvector. The purpose of this project is to figure out how we can better integrate with existing python frameworks and tooling.

## Idea
The idea is to provide a small service that keeps track of a code base through file watchers in postgres and embeds the files. You can then use these embeddings to find relevant code files for any LLM queries related to improvements on that code base without having to manually copy all the related code for it each time.

Changes you make based on those results will then immediately propagate into the store -> repeat.

Status:
Currently there is a single API endpoint that allows to send a query and retrieve relevant code files based on the query (see tests for how it works).

# Installation
This project uses `uv` so `uv sync` and `uv run pytest` should get you going.

## Useful commands
### Run migrations
```bash
uv run alembic upgrade head
```

### Run the server
```bash
uv run fastapi dev main.py
```

### Run tests
```bash
uv run pytest
```

### Run linting
```bash
uv run ruff format
uv run ruff check --fix
```

### Run type checking
```bash
uv run pyright
```
