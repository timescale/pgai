# pgai documentation

A Python library that turns PostgreSQL into the retrieval engine behind robust, production-ready RAG and Agentic applications.

- 🔄 Automatically create vector embeddings from data in PostgreSQL tables as well as documents in S3.  The embeddings are automatically updated as the data changes.

- 🔍 Powerful vector and semantic search with pgvector and pgvectorscale.

- 🛡️ Production-ready out-of-the-box: Supports batch processing for efficient embedding generation, with built-in handling for model failures, rate limits, and latency spikes.

Works with any PostgreSQL database, including Timescale Cloud, Amazon RDS, Supabase and more.

## pgai install

The pgai python library can be installed using pip:

```bash
pip install pgai
```

To setup the necessary database functions and tables in your PostgreSQL database, run the following python code:

```python
from pgai
pgai.install(DB_URL)
```

All of the pgai objects are installed into the `ai` schema.

## pgai Vectorizer

Vectorizer automates the embedding process within your database management by treating embeddings as a declarative, DDL-like feature — like an index.

 **Overview**: [Automate AI embedding with pgai Vectorizer](vectorizer/overview.md) - a comprehensive overview of Vectorizer features, demonstrating how it streamlines the process of working with vector embeddings in your database.
- **Quickstart guides**:
  * [Vectorizer quickstart for Ollama](vectorizer/quick-start.md): setup your developer environment, create and run a vectorizer.
  * [Vectorizer quickstart for OpenAI](vectorizer/quick-start-openai.md): setup your developer environment, create and run a vectorizer using OpenAI.
  * [Vectorizer quickstart for Voyage](vectorizer/quick-start-voyage.md): setup your developer environment, create and run a vectorizer using Voyage. 
- **References**:
  * [pgai Vectorizer API reference](vectorizer/api-reference.md): API reference for Vectorizer functions 
  * [Documentation for vectorizer worker](vectorizer/worker.md): explain how to run vectorizers on a self-hosted PostgreSQL instance.
  * [SqlAlchemy and Alembic integration](vectorizer/python-integration.md): learn how to use Vectorizer with SqlAlchemy and Alembic.
- **Develop**:
  * [Add a Vectorizer embedding integration](vectorizer/adding-embedding-integration.md)

## pgai utils
  * [Chunking](/docs/utils/chunking.md): chunking algorithms you can use from withinSQL.

## pgai extension

The pgai extension is a PostgreSQL extension that performs model calling inside of PostgreSQL. You can find more information about the extension in the [pgai extension directory](/projects/extension/README.md).