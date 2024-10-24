
<p></p>
<div align=center>

# pgai

<h3>Semantic search and RAG application development directly in Postgres</h3>

[![Discord](https://img.shields.io/badge/Join_us_on_Discord-black?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/KRdHVXAmkp)
[![Try Timescale for free](https://img.shields.io/badge/Try_Timescale_for_free-black?style=for-the-badge&logo=timescale&logoColor=white)](https://tsdb.co/gh-pgai-signup)
</div>

pgai is a Postgres extension that provides easy to use SQL functions that enable you to populate
[pgvector](https://github.com/pgvector/pgvector) embeddings directly in your database. pgai enables you to:

* [Automatically create and sync LLM embeddings for your data](#automatically-create-and-sync-llm-embeddings-for-your-data)
* [Search your data using vector and semantic search](#search-your-data-using-vector-and-semantic-search)
* [Implement Retrieval Augmented Generation inside a single SQL statement](#implement-retrieval-augmented-generation-inside-a-single-sql-statement) 

When you install pgai on Timescale Cloud, you use scheduling to control the times when vectorizers 
are run. On a self-hosted Postgres installation, you use pgai vectorizer worker to asynchronously processes 
your vectorizers.

* **TL;DR**:
  * [Try out automatic embedding vectorization](/docs/vectorizer-quick-start.md): quickly create embeddings using
    a pre-built Docker developer environment with a self-hosted Postgres instance with pgai and our vectorizer worker
    installed. This takes less than 10 minutes!
* **Everyone**: Use pgai in your PostgreSQL database.
  1. [Install pgai](#installation) in Timescale Cloud, a pre-built Docker image or from source.
  1. [Automate AI embedding with pgai Vectorizer](/docs/vectorizer.md)
  1. Use pgai to integrate AI from your provider:
     * [Ollama](./docs/ollama.md) - configure pgai for Ollama, then use the model to embed, chat complete and generate.
     * [OpenAI](./docs/openai.md) - configure pgai for OpenAI, then use the model to tokenize, embed, chat complete and moderate. This page also includes advanced examples.
     * [Anthropic](./docs/anthropic.md) - configure pgai for Anthropic, then use the model to generate content.
     * [Cohere](./docs/cohere.md) - configure pgai for Cohere, then use the model to tokenize, embed, chat complete, classify, and rerank.
  1. Reason over your data and facilitate use cases like [classification, summarization, and data enrichment](/docs/openai.md) on your existing relational data in PostgreSQL.
* **Extension contributor**: Contribute to pgai and improve the project.
  * [Develop and test changes to the pgai extension](./DEVELOPMENT.md).
  * See the [Issues tab](https://github.com/timescale/pgai/issues) for a list of feature ideas to contribute.

**Learn more about pgai:** To learn more about the pgai extension and why we built it, read 
[pgai: Giving PostgreSQL Developers AI Engineering Superpowers](http://www.timescale.com/blog/pgai-giving-postgresql-developers-ai-engineering-superpowers).


## Features

The main features in pgai are:

* [Automatically create and sync LLM embeddings for your data](#automatically-create-and-sync-llm-embeddings-for-your-data)
* [Search your data using vector and semantic search](#search-your-data-using-vector-and-semantic-search)
* [Implement Retrieval Augmented Generation inside a single SQL statement](#implement-retrieval-augmented-generation-inside-a-single-sql-statement)

### Automatically create and sync LLM embeddings for your data

pgai builds on the Timescale [pgvector](https://github.com/pgvector/pgvector) and 
[pgvectorscale](https://github.com/timescale/pgvectorscale) extensions to automatically create and 
synchronizes embeddings for your data, and make searching even faster.

With one line of code, you can define a vectorizer that creates embeddings for data in a table:
```sql
SELECT ai.create_vectorizer( 
    <table_name>::regclass,
    destination => <embedding_table_name>,
    embedding => ai.embedding_openai(<model_name>, <dimensions>),
    chunking => ai.chunking_recursive_character_text_splitter(<column_name>)
);
```

[Automate AI embedding with pgai Vectorizer](/docs/vectorizer.md) shows you how to implement embeddings 
in your own data. When you install pgai on Timescale Cloud, you use scheduling to control vectorizer run times. 
On a self-hosted Postgres installation, you use [Vectorizer Worker](/docs/vectorizer-worker.md) to asynchronously 
processes your vectorizers.

### Search your data using vector and semantic search

pgai exposes a set of functions to directly interact with the llm models through SQL, enabling 
you to do semantic search directly in your database:

```sql
SELECT 
   chunk,
   embedding <=> ai.openai_embed(<embedding_model>, 'some-query') as distance
FROM <embedding_table>
ORDER BY distance
LIMIT 5;
```

This is a perfectly normal SQL query. You can combine it with `where` clauses and other SQL features to 
further refine your search. pgai solves the *missing where clause in vector search* problem for real.

### Implement Retrieval Augmented Generation inside a single SQL statement

Similar to [semantic search](#search-your-data-using-vector-and-semantic-search), pgai LLM functions 
enable you to implement RAG directly in your database. For example:

1. Create a RAG function:
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

1. Execute your function in a SQL query:

    ```sql
    SELECT generate_rag_response('Give me some startup advice');-*_
    ```

## Installation

The fastest way to run PostgreSQL with the pgai extension are to:

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
