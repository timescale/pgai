
# Overview

This document describes how to create and run vectorizers from Python.

# Installation

First, install the pgai library:
```bash
pip install pgai
```

Then, you need to install the necessary database tables and functions. All database objects will be created in the `ai` schema. This is done by running the following Python code:

```python
import pgai

pgai.install(DB_URL)
```

# Creating vectorizers from python

To help you create vectorizers from python, pgai provides the `CreateVectorizer` helper class. This class makes it easy to generate the `create_vectorizer` SQL statement, by giving you a pythonic interface.
It accepts all the options listed in the [SQL API](/docs/vectorizer/api-reference.md) and exposes the `to_sql`
method to generate a SQL query which you can then run through the SQL library of your choice:

```python
from pgai.vectorizer import CreateVectorizer
from pgai.vectorizer.configuration import EmbeddingOpenaiConfig, ChunkingCharacterTextSplitterConfig, FormattingPythonTemplateConfig, LoadingColumnConfig, DestinationTableConfig

vectorizer_statement = CreateVectorizer(
    source="blog",
    name="blog_content_embedder",  # Optional custom name for easier reference
    destination=DestinationTableConfig(
        destination='blog_embeddings'
    ),
    loading=LoadingColumnConfig(column_name='content'),
    embedding=EmbeddingOpenaiConfig(
        model='text-embedding-3-small',
        dimensions=768
    ),
    chunking=ChunkingCharacterTextSplitterConfig(
        chunk_size=800,
        chunk_overlap=400,
        separator='.',
        is_separator_regex=False
    ),
    formatting=FormattingPythonTemplateConfig(template='$title - $chunk')
).to_sql()
```

Then, you can run this statement using the PostgreSQL library of your choice. For example, using the [`psycopg`](https://www.psycopg.org/psycopg3/docs/) library:

```python
import psycopg

with psycopg.connect(conn_string) as conn:
    with conn.cursor() as cursor:
        cursor.execute(vectorizer_statement)
```

# Running the vectorizer worker

You can then run the vectorizer worker using the the CLI tool or the `Worker` class discussed in the [vectorizer worker documentation](/docs/vectorizer/worker.md).

# Related integrations

- [SQLAlchemy integration](/docs/vectorizer/sqlalchemy-integration.md)
- [Alembic integration](/docs/vectorizer/alembic-integration.md)
