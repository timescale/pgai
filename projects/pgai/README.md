<p align="center">
    <img height="200" src="https://github.com/timescale/pgai/blob/main/docs/images/pgai_logo.png?raw=true" alt="pgai"/>
</p>

<p></p>
<div align=center>

<h3>Power your RAG and Agentic applications with PostgreSQL</h3>

<div>
  <a href="https://github.com/timescale/pgai/tree/main/docs"><strong>Docs</strong></a> ·
  <a href="https://discord.gg/KRdHVXAmkp"><strong>Join the pgai Discord!</strong></a> ·
  <a href="https://tsdb.co/gh-pgai-signup"><strong>Try timescale for free!</strong></a> ·
  <a href="https://github.com/timescale/pgai/releases"><strong>Changelog</strong></a>
</div>
</div>
<br/>

A Python library that transforms PostgreSQL into a robust, production-ready retrieval engine for RAG and Agentic applications.

- 🔄 Automatically create and synchronize vector embeddings from PostgreSQL data and S3 documents. Embeddings update automatically as data changes.

- 🔍 Powerful vector and semantic search with pgvector and pgvectorscale.

- 🛡️ Production-ready out-of-the-box: Supports batch processing for efficient embedding generation, with built-in handling for model failures, rate limits, and latency spikes.

- 🐘 Works with any PostgreSQL database, including Timescale Cloud, Amazon RDS, Supabase and more.

# Getting Started

Install:

```bash
pip install pgai
```

```bash
pgai install -d "postgresql://postgres:postgres@localhost:5432/postgres"
```

The key "secret sauce" of pgai Vectorizer is its declarative approach to
embedding generation. Simply define your pipeline and let Vectorizer handle the
operational complexity of keeping embeddings in sync, even when embedding
endpoints are unreliable. You can define a simple version of the pipeline as
follows:

```sql
SELECT ai.create_vectorizer(
     'wiki'::regclass,
     loading => ai.loading_column(column_name=>'text'),
     embedding => ai.embedding_openai(model=>'text-embedding-ada-002', dimensions=>'1536'),
     destination => ai.destination_table(target_table=>'wiki_embedding_storage')
    )
```

The vectorizer will automatically create embeddings for all the rows in the
`wiki` table, and, more importantly, will keep the embeddings synced with the
underlying data as it changes.  **Think of it almost like declaring an index** on
the `wiki` table, but instead of the database managing the index datastructure
for you, the vectorizer is managing the embeddings. 

Checkout our full quick start on [github](https://github.com/timescale/pgai#quick-start)
