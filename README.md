
<p></p>
<div align=center>

# pgai

<h3>Semantic search and RAG application development directly in Postgres</h3>

[![Discord](https://img.shields.io/badge/Join_us_on_Discord-black?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/KRdHVXAmkp)
[![Try Timescale for free](https://img.shields.io/badge/Try_Timescale_for_free-black?style=for-the-badge&logo=timescale&logoColor=white)](https://tsdb.co/gh-pgai-signup)
</div>

pgai enables building [search](https://en.wikipedia.org/wiki/Similarity_search), and
[Retrieval Augmented Generation](https://en.wikipedia.org/wiki/Prompt_engineering#Retrieval-augmented_generation) (RAG) applications directly in PostgreSQL.

# Overview
pgai is a postgres extension that allows you to:

* Automatically create and sync LLM embeddings for your data.
* Search in your data using vector/semantic search.
* Do Retrieval Augmented Generation inside of a single SQL statement.

It does this by providing an easy to use interface in the form of SQL functions that allows you to populate [pgvector](https://github.com/pgvector/pgvector) embeddings directly from your database.

pgai also ships with a worker that makes sure to asynchronously reconcile your data with the embedding store in the background.

# Getting Started  
* Check out our self-hosted quick start Guide here: [Quick Start Guide](/docs/vectorizer-quick-start.md)  
* Or head over to our cloud offering and create a **free** trial account: [Timescale Cloud](https://tsdb.co/gh-pgai-signup)

# Documentation

## Features

### Automatic Embedding generation and synchronization
pgai automatically creates and synchronizes embeddings for your data making use of the [pgvector](https://github.com/pgvector/pgvector) extension. We also include our own vector index [pgvectorscale](https://github.com/timescale/pgvectorscale) to make searching in your data even faster.

To start you need to define a vectorizer for the table for which you want to create embeddings:
```sql
SELECT ai.create_vectorizer( 
    <table_name>::regclass,
    destination => <embedding_table_name>,
    embedding => ai.embedding_openai(<model_name>, <dimensions>),
    chunking => ai.chunking_recursive_character_text_splitter(<column_name>)
);
```
You can read the details of how to customize this vectorizer to your needs here: [Vectorizer](/docs/vectorizer.md).

If you are not using our cloud offering, you need to run our worker to actually generate the embeddings and store them in the vector store. You can read more about the worker here: [Vectorizer Worker](/docs/vectorizer-worker.md).

### Semantic Search
pgai also exposes a set of functions to directly interact with the llm models through sql, this allows you to do semantic search directly in your database:
```sql
SELECT 
   chunk,
   embedding <=> ai.openai_embed(<embedding_model>, 'some-query') as distance
FROM <embedding_table>
ORDER BY distance
LIMIT 5;
```
Note that this is a perfectly normal SQL query so you can combine it with `where` clauses and other SQL features to further refine your search. This solves the "The missing where clause in vector search"-problem for real.

### Retrieval Augmented Generation
In a similar fashion to the semantic search the LLM functions allow you to implement RAG directly in your database e.g. you can define a function like so:
```sql
CREATE OR REPLACE FUNCTION generate_rag_response(query_text TEXT)
RETURNS TEXT AS $$
DECLARE
   context_chunks TEXT;
   response TEXT;
BEGIN
   -- Perform similarity search to find relevant blog posts
   SELECT string_agg(title || ': ' || chunk, ' ') INTO context_chunks
   FROM (
       SELECT title, chunk
       FROM blogs_embedding
       ORDER BY embedding <=> ai.openai_embed('text-embedding-3-small', query_text)
       LIMIT 3
   ) AS relevant_posts;

   -- Generate a summary using gpt-4o-mini
   SELECT ai.openai_chat_complete(
       'gpt-4o-mini',
       jsonb_build_array(
           jsonb_build_object('role', 'system', 'content', 'You are a helpful assistant. Use only the context provided to answer the question. Also mention the titles of the blog posts you use to answer the question.'),
           jsonb_build_object('role', 'user', 'content', format('Context: %s\n\nUser Question: %s\n\nAssistant:', context_chunks, query_text))
       )
   )->'choices'->0->'message'->>'content' INTO response;
  
   RETURN response;
END;
$$ LANGUAGE plpgsql;
```

And then execute it like this:
```sql
SELECT generate_rag_response('Give me some startup advice');-*_
```

### Limitations
Embedding generation is currently only supported for openai models. But we have already implemented helper functions for a bunch of other models that you can play around with and build on top. See the individual docs for details:

* `ai.openai_...` - [pgai OpenAI features](/docs/openai.md)
* `ai.ollama_...` - [pgai Ollama features](/docs/ollama.md)
* `ai.cohere_...` - [pgai Cohere features](/docs/cohere.md)
* `ai.anthropic_...` - [pgai Anthropic features](/docs/anthropic.md)

We will use these functions ourselves to implement embedding generation for other models soon.


## Installation

The fastest ways to run PostgreSQL with the pgai extension are to:

1. Create your database environment. Either:
   * [Use a pre-built Docker container](#use-a-pre-built-docker-container).
   * [Use a Timescale Cloud service](#use-a-timescale-cloud-service).
   * [Install from source](#install-from-source).

2. [Enable the pgai extension](#enable-the-pgai-extension-in-your-database).

3. [Use pgai](#use-pgai).

### Use a pre-built Docker container

[Run the TimescaleDB Docker image](https://docs.timescale.com/self-hosted/latest/install/installation-docker/), then
[enable the pgai extension](#enable-the-pgai-extension-in-your-database).

### Use a Timescale Cloud service

pgai is available for [new][create-a-new-service] or existing Timescale Cloud services. For any service,
[enable the pgai extension](#enable-the-pgai-extension-in-your-database).


### Install from source

To install pgai from source on a PostgreSQL server:

1. **Install the prerequisite software system-wide**
   - **Python3**: if running `python3 --version` in Terminal returns `command
     not found`, download and install the latest version of [Python3][python3].

   - **Pip**: if running `pip --version` in Terminal returns `command not found`:
     - **Standard installation**: use one of the pip [supported methods][pip].
     - **Virtual environment**: usually, pip is automatically installed if you are working in a
       [Python virtual environment][python-virtual-environment]. If you are running PostgreSQL in a virtual
       environment, pgai requires several python packages. Set the `PYTHONPATH` and `VIRTUAL_ENV`
       environment variables before you start your PostgreSQL server.

       ```bash
       PYTHONPATH=/path/to/venv/lib/python3.12/site-packages \
       VIRTUAL_ENV=/path/to/venv \
       pg_ctl -D /path/to/data -l logfile start
       ```
   - **PL/Python**: follow [How to install Postgres 16 with plpython3u: Recipes for macOS, Ubuntu, Debian, CentOS, Docker][pgai-plpython].

      _macOS_: the standard PostgreSQL brew in Homebrew does not include the `plpython3` extension. These instructions show
      how to install from an alternate tap.

     - **[Postgresql plugin][asdf-postgres] for the [asdf][asdf] version manager**: set the `--with-python` option
       when installing PostgreSQL:

       ```bash
       POSTGRES_EXTRA_CONFIGURE_OPTIONS=--with-python asdf install postgres 16.3
       ```

   - **pgvector**: follow the [install instructions][pgvector-install] from the official repository.

   These extensions are automatically added to your PostgreSQL database when you
   [Enable the pgai extension](#enable-the-pgai-extension-in-your-database).

1. Make this `pgai` extension:

    ```bash
    make install
    ```
1. [Enable the pgai extension](#enable-the-pgai-extension-in-your-database).

### Enable the pgai extension in your database

1. Connect to your database with a postgres client like [psql v16](https://docs.timescale.com/use-timescale/latest/integrations/query-admin/psql/)
   or [PopSQL](https://docs.timescale.com/use-timescale/latest/popsql/).
   ```bash
   psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>"
   ```

3. Create the pgai extension:

    ```sql
    CREATE EXTENSION IF NOT EXISTS ai CASCADE;
    ```

   The `CASCADE` automatically installs `pgvector` and `plpython3u` extensions.

### Use pgai

Now, use pgai to integrate AI from [Ollama](./docs/ollama.md) and [OpenAI](./docs/openai.md).
Learn how to [moderate](./docs/moderate.md) and [embed](./docs/delayed_embed.md)
content directly in the database using triggers and background jobs.

## Get involved

pgai is still at an early stage. Now is a great time to help shape the direction of this project;
we are currently deciding priorities. Have a look at the [list of features](https://github.com/timescale/pgai/issues) we're thinking of working on.
Feel free to comment, expand the list, or hop on the Discussions forum.

To get started, take a look at [how to contribute](./CONTRIBUTING.md)
and [how to set up a dev/test environment](./DEVELOPMENT.md).

## About Timescale

Timescale is a PostgreSQL database company. To learn more visit the [timescale.com](https://www.timescale.com).

Timescale Cloud is a high-performance, developer focused, cloud platform that provides PostgreSQL services
for the most demanding AI, time-series, analytics, and event workloads. Timescale Cloud is ideal for production applications and provides high availability, streaming backups, upgrades over time, roles and permissions, and great security.

[pgai-plpython]: https://github.com/postgres-ai/postgres-howtos/blob/main/0047_how_to_install_postgres_16_with_plpython3u.md
[asdf-postgres]: https://github.com/smashedtoatoms/asdf-postgres
[asdf]: https://github.com/asdf-vm/asdf
[python3]: https://www.python.org/downloads/
[pip]: https://pip.pypa.io/en/stable/installation/#supported-methods
[plpython3u]: https://www.postgresql.org/docs/current/plpython.html
[pgvector]: https://github.com/pgvector/pgvector
[pgvector-install]: https://github.com/pgvector/pgvector?tab=readme-ov-file#installation
[python-virtual-environment]: https://packaging.python.org/en/latest/tutorials/installing-packages/#creating-and-using-virtual-environments
[create-a-new-service]: https://console.cloud.timescale.com/dashboard/create_services
