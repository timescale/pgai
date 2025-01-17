
<p align="center">
    <img height="200" src="docs/images/pgai_logo.png" alt="pgai"/>
</p>

<div align=center>

<h3>Power your AI applications with PostgreSQL</h3>

[![Discord](https://img.shields.io/badge/Join_us_on_Discord-black?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/KRdHVXAmkp)
[![Try Timescale for free](https://img.shields.io/badge/Try_Timescale_for_free-black?style=for-the-badge&logo=timescale&logoColor=white)](https://tsdb.co/gh-pgai-signup)
</div>

Supercharge your PostgreSQL database with AI capabilities. Supports:  

- Automatic creation and synchronization of vector embeddings for your data  
- Seamless vector and semantic search  
- Retrieval Augmented Generation (RAG) directly in SQL
- Ability to call out to leading LLMs like OpenAI, Ollama, Cohere, and more via SQL.
- Built-in utilities for dataset loading and processing 

All with the reliability, scalability, and ACID compliance of PostgreSQL. 

<div align=center>

[![Auto Create and Sync Vector Embeddings in 1 Line of SQL (pgai Vectorizer)](https://github.com/user-attachments/assets/8a71c774-505a-4335-8b34-cdea9dedb558)](https://youtu.be/ZoC2XYol6Zk?si=atI4XPurEifG0pd5)

</div>


### Docker

See the [install via docker](/docs/install_docker.md) guide for docker compose files and detailed container instructions.

### Timescale Cloud

Try pgai on cloud by creating a [free trial account](https://tsdb.co/gh-pgai-signup) on Timescale Cloud. 


### Installing pgai into an existing PostgreSQL instance (Linux / MacOS)

See the [install from source](/docs/install_from_source.md) guide for instructions on how to install pgai from source.                  

# Quick Start

This section will walk you through the steps to get started with pgai and Ollama using docker and show you the major features of pgai. 

Please note that using Ollama requires a large (>4GB) download of the docker image and model. If you don't want to download so much data, you may want to use the [OpenAI quick start](/docs/vectorizer-quick-start-openai.md) or [VoyageAI quick start](/docs/vectorizer-quick-start-voyage.md) instead.

### Setup

1. **Download the [docker compose file](/examples/docker_compose_pgai_ollama/docker-compose.yml) file.**

    ```
    curl -O https://raw.githubusercontent.com/timescale/pgai/main/examples/docker_compose_pgai_ollama/docker-compose.yml
    ```

1. **Start the docker compose file.**
    ```
    docker compose up -d
    ```


    This will start Ollama and a PostgreSQL instance with the pgai extension installed. 
  
1. **Download the Ollama models.** We'll use the `all-minilm` model for embeddings and the `tinyllama` model for reasoning.

    ```
    docker compose exec ollama ollama pull all-minilm
    docker compose exec ollama ollama pull tinyllama
    ```

### Create a table, run a vectorizer, and perform semantic search

1. **Connect to the database in your local developer environment**
   The easiest way connect to the database is with the following command:
   `docker compose exec -it db psql`. 
   
   Alternatively, you can connect to the database with the following connection string: `postgres://postgres:postgres@localhost:5432/postgres`.

1. **Enable pgai on your database**

    ```sql
    CREATE EXTENSION IF NOT EXISTS ai CASCADE;
    ```
    
1. **Create a table with the data you want to embed from a huggingface dataset**

    We'll create a table named `wiki` from a few rows of the english-language `wikimedia/wikipedia` dataset.

    ```sql
    SELECT ai.load_dataset('wikimedia/wikipedia', '20231101.en', table_name=>'wiki', batch_size=>5, max_batches=>1);
    ```
    
    Related documentation: [load dataset from huggingface](/docs/load_dataset_from_huggingface.md).
    
    This table will contain the following columns: `id`, `url`, `title`, `text`. We'll create a primary key on the `id` column:

    ```sql
    ALTER TABLE wiki ADD PRIMARY KEY (id);
    ```

1. **Create a vectorizer for `wiki`**

    To enable semantic search on the `wiki` table, we need to create vector embeddings for the `text` column.
    We use a vectorizer to automatically create these embeddings and keep them in sync with the data in the  `wiki` table.
    
    ```sql
    SELECT ai.create_vectorizer(
         'wiki'::regclass,
         destination => 'wiki_embeddings',
         embedding => ai.embedding_ollama('all-minilm', 384),
         chunking => ai.chunking_recursive_character_text_splitter('text')
    );
    ```
    
     Related documentation: [vectorizer usage guide](/docs/vectorizer.md) and [vectorizer API reference](/docs/vectorizer-api-reference.md).
    
    
1. **Check the progress of the vectorizer embedding creation**

    ```sql
    select * from ai.vectorizer_status;
    ```
 
    The output will look like this:


    | id | source_table | target_table | view | pending_items |
    |----|--------------|--------------|------|---------------|
    | 1 | public.wiki | public.wiki_embeddings_store | public.wiki_embeddings | 10000 |
    
    All the embeddings have been created when the `pending_items` column is 0. This may take a few minutes as the model is running locally and not on a GPU.
    
1. **Search the embeddings**

    We'll search the embeddings for the concept of "properties of light" even though these words are not in the text of the articles. This is possible because vector embeddings capture the semantic meaning of the text.
    
    Semantic search is a powerful feature in its own right, but it is also a key component of Retrieval Augmented Generation (RAG).

    ```sql
    SELECT title, chunk
    FROM wiki_embeddings 
    ORDER BY embedding <=> ai.ollama_embed('all-minilm', 'properties of light')
    LIMIT 1;
    ```
    
    This query selects from the `wiki_embeddings` view, which is created by the vectorizer and joins the embeddings with the original data in the `wiki` table to give us the ability to search using the embeddings but still be able to access (or filter on) all the data in the original table (e.g. the `title` column).
    
    Note the `ai.ollama_embed` function is used to call the `all-minilm` model. This is part of pgai's  [model calling capabilities](#model-calling).

    The output will look like this:
    
    | title | chunk |
    |-------|-------|
    | Albedo |  Water reflects light very differently from typical terrestrial materials. The reflectivity of a water surface is calculated using the Fresnel equations.... |
 
 1. **Modify your data and have the vectorizer automatically update the embeddings**
 
    We'll add a row about pgai to the `wiki` table and have the vectorizer automatically update the embeddings.
    
    ```sql
    INSERT INTO wiki (id, url, title, text) VALUES (11,'https://en.wikipedia.org/wiki/Pgai', 'pgai - Power your AI applications with PostgreSQL', 'pgai is a tool to make developing RAG and other AI applications easier. It makes it simple to give an LLM access to data in your PostgreSQL database by enabling semantic search on your data and using the results as part of the Retrieval Augmented Generation (RAG) pipeline. This allows the LLM to answer questions about your data without needing to being trained on your data.');
    ```
    And now you don't need to do anything to update the embeddings. The vectorizer will automatically create the embeddings for the new row without any intervention from you. After a few seconds, you can run a search query related to the new entry and see it returned as part of the results:
    
    ```sql
    SELECT title, chunk
    FROM wiki_embeddings 
    ORDER BY embedding <=> ai.ollama_embed('all-minilm', 'AI tools')
    LIMIT 1;
    ```
### Perform Retrieval Augmented Generation (RAG)

**Use RAG to answer questions about pgai**

We'll create a function that uses RAG to allow an LLM to answer questions about pgai based on the wiki entry we added.

RAG involves two steps:
1. Perform a similarity search to find the most relevant chunks of data.
2. Use the LLM to generate a response using the relevant chunks as context.

```sql
CREATE OR REPLACE FUNCTION generate_rag_response(query_text TEXT)
RETURNS TEXT AS $$
DECLARE
    context_chunks TEXT;
    response JSONB;
BEGIN
    -- Perform similarity search to find relevant wiki article
    SELECT string_agg(title || ': ' || chunk, E'\n') INTO context_chunks
    FROM
    (
        SELECT title, chunk
        FROM wiki_embeddings 
        ORDER BY embedding <=> ai.ollama_embed('all-minilm', query_text)
        LIMIT 1
    ) AS relevant_posts;

    raise notice 'Context provided to LLM: %', context_chunks;
    
    -- Generate a summary using tinyllama
    select ai.ollama_generate('tinyllama', 
    query_text || E'\nUse the following context to respond.\n' || context_chunks) INTO response;

    RETURN response->>'response';
END;
$$ LANGUAGE plpgsql;
```

Then, we can use the function to answer questions about the wiki data.

```sql
SELECT generate_rag_response('What can I use pgai for?') as response; 
```

The output will look like this:

| response |
|-----------------------|
|   PGAI is a tool that makes it easier for developers to create AI applications by providing access to data in a PostgreSQL database using Semantic Search and answering RAG (Recommendation and Answer Generation) questions. This allows the LLM (Language Model) to answer questions about unseen data without being trained on your data, making it an important tool for building accurate and efficient AI applications. The context suggests that PGAI can be useful in a variety of industries or use cases where data access is critical, such as healthcare, finance, or customer service. |


### Generate a summary of the article in the database
**Generate a summary of the article in the database**

We'll generate a summary of the search results using the `ai.ollama_generate` function (this will take a few minutes).

```sql
SELECT answer->>'response' as summary
FROM ai.ollama_generate('tinyllama', 
'Summarize the following and output the summary in a single sentence: '|| (SELECT text FROM wiki WHERE title like 'pgai%')) as answer;
```

The output will look like this:

| summary |
|--------------------------------|
| Pgai is a tool that simplifies the process of making AI applications easier by providing easy access to data in PostgreSQL and enabling semantic search on the data for the Retrieval Augmented Generation (RAG) pipeline. This allows the AI system to answer questions about unseen data without being trained on it, simplifying the entire process. |

This is just one example of [model calling capabilities](#model-calling). Model calling can be used for a variety of tasks, including classification, summarization, moderation, and other forms of data enrichment. 
    
# Features 

## Work with embeddings generated from your data
* Automatically create and sync vector embeddings for your data ([learn more](#automatically-create-and-sync-llm-embeddings-for-your-data))
* Search your data using vector and semantic search ([learn more](#search-your-data-using-vector-and-semantic-search))
* Implement Retrieval Augmented Generation inside a single SQL statement ([learn more](#implement-retrieval-augmented-generation-inside-a-single-sql-statement))
* Perform high-performance, cost-efficient ANN search on large vector workloads with [pgvectorscale](https://github.com/timescale/pgvectorscale), which complements pgvector.

## Leverage LLMs for data processing tasks
* Retrieve LLM chat completions from models like Claude Sonnet 3.5, OpenAI GPT4o, Cohere Command, and Llama 3 (via Ollama). ([learn more](#usage-of-pgai))
* Reason over your data and facilitate use cases like classification, summarization, and data enrichment on your existing relational data in PostgreSQL ([see an example](/docs/openai.md)).

## Useful utilities
* Load datasets from Hugging Face into your database with [ai.load_dataset](/docs/load_dataset_from_huggingface.md).

# Resources
## Why we built it
- [Vector Databases Are the Wrong Abstraction](https://www.timescale.com/blog/vector-databases-are-the-wrong-abstraction/)
- [pgai: Giving PostgreSQL Developers AI Engineering Superpowers](http://www.timescale.com/blog/pgai-giving-postgresql-developers-ai-engineering-superpowers)

## Quick start guides
- [The quick start with Ollama guide above](#quick-start)
- [Quick start with OpenAI](/docs/vectorizer-quick-start-openai.md)
- [Quick start with VoyageAI](/docs/vectorizer-quick-start-voyage.md)

## Tutorials about pgai vectorizer
- [How to Automatically Create & Update Embeddings in PostgreSQL—With One SQL Query](https://www.timescale.com/blog/how-to-automatically-create-update-embeddings-in-postgresql/)
- [video] [Auto Create and Sync Vector Embeddings in 1 Line of SQL](https://www.youtube.com/watch?v=ZoC2XYol6Zk)
- [Which OpenAI Embedding Model Is Best for Your RAG App With Pgvector?](https://www.timescale.com/blog/which-openai-embedding-model-is-best/)
- [Which RAG Chunking and Formatting Strategy Is Best for Your App With Pgvector](https://www.timescale.com/blog/which-rag-chunking-and-formatting-strategy-is-best/)
- [Parsing All the Data With Open-Source Tools: Unstructured and Pgai](https://www.timescale.com/blog/parsing-all-the-data-with-open-source-tools-unstructured-and-pgai/)

## Tutorials about pgai model calling
- [In-Database AI Agents: Teaching Claude to Use Tools With Pgai](https://www.timescale.com/blog/in-database-ai-agents-teaching-claude-to-use-tools-with-pgai/)
- [Build Search and RAG Systems on PostgreSQL Using Cohere and Pgai](https://www.timescale.com/blog/build-search-and-rag-systems-on-postgresql-using-cohere-and-pgai/)
- [Use Open-Source LLMs in PostgreSQL With Ollama and Pgai](https://www.timescale.com/blog/use-open-source-llms-in-postgresql-with-ollama-and-pgai/)

## Contributing
We welcome contributions to pgai! See the [Contributing](/CONTRIBUTING.md) page for more information.

# Automated embedding and semantic search

* [Automatically create and sync vector embeddings for your data](#automatically-create-and-sync-llm-embeddings-for-your-data)
* [Search your data using vector and semantic search](#search-your-data-using-vector-and-semantic-search)
* [Implement Retrieval Augmented Generation inside a single SQL statement](#implement-retrieval-augmented-generation-inside-a-single-sql-statement)

### Automatically create and sync LLM embeddings for your data

The [pgvector](https://github.com/pgvector/pgvector) and
[pgvectorscale](https://github.com/timescale/pgvectorscale) extensions allow you
to store vector embeddings in your database and perform fast and efficient
vector search.  The [pgai Vectorizer](/docs/vectorizer.md) builds on top of
these extensions to automatically create and synchronize embeddings for any
text data in your database.

With one line of code, you can define a vectorizer that creates embeddings for data in a table:
```sql
SELECT ai.create_vectorizer(
    <table_name>::regclass,
    destination => <embedding_table_name>,
    embedding => ai.embedding_ollama(<model_name>, <dimensions>),
    chunking => ai.chunking_recursive_character_text_splitter(<column_name>)
);
```
This newly created vectorizer will automatically track any changes to the
data in the source table and update the destination embedding table
with the new embeddings asynchronously.

[Automate AI embedding with pgai Vectorizer](/docs/vectorizer.md) shows you how
to implement embeddings in your own data. On a self-hosted Postgres
installation, you use a [Vectorizer Worker](/docs/vectorizer-worker.md) to
asynchronously processes your vectorizers. When you create Vectorizers in a
Timescale Cloud database, embeddings are automatically created and synchronized
in the background.

Note: Timescale Cloud currently supports embedding natively with OpenAI. To use Ollama on the data in your Timescale Cloud service, set [scheduling => ai.scheduling_none()](/docs/vectorizer-api-reference.md#scheduling-configuration) in the configuration for your service, then [install the vectorizer worker locally](/docs/vectorizer-worker.md#install-and-configure-vectorizer-worker) and configure it to connect to your Timescale Cloud service.

### Search your data using vector and semantic search

pgai exposes a set of functions to directly interact with the LLM models through SQL, enabling
you to do semantic search directly in your database:

```sql
SELECT
   chunk,
   embedding <=> ai.ollama_embed(<embedding_model>, 'some-query') as distance
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
       SELECT string_agg(title || ': ' || chunk, E'\n') INTO context_chunks
       FROM
       (
           SELECT title, chunk
           FROM blogs_embedding
           ORDER BY embedding <=> ai.ollama_embed('nomic-embed-text', query_text)
           LIMIT 3
       ) AS relevant_posts;

       -- Generate a summary using llama3
       SELECT ai.ollama_chat_complete
       ( 'llama3'
       , jsonb_build_array
         ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
         , jsonb_build_object
           ('role', 'user'
           , 'content', query_text || E'\nUse the following context to respond.\n' || context_chunks
           )
         )
       )->'message'->>'content' INTO response;

       RETURN response;
    END;
    $$ LANGUAGE plpgsql;
    ```

1. Execute your function in a SQL query:

    ```sql
    SELECT generate_rag_response('Give me some startup advice');
    ```

## Model calling

Model calling is a feature of pgai that allows you to call LLM models from SQL. This lets you leverage the power of LLMs for a variety of tasks, including classification, summarization, moderation, and other forms of data enrichment.

The following models are supported (click on the model to learn more):

| **Model**                                            | **Tokenize** | **Embed** | **Chat Complete** | **Generate** | **Moderate** | **Classify** | **Rerank** |
|------------------------------------------------------|:------------:|:---------:|:-----------------:|:------------:|:------------:|:------------:|:----------:|
| **[Ollama](./docs/ollama.md)**                       |              |    ✔️     |        ✔️         |      ✔️      |              |              |            |
| **[OpenAI](./docs/openai.md)**                       |     ✔️️      |    ✔️     |        ✔️         |              |      ✔️      |              |            |
| **[Anthropic](./docs/anthropic.md)**                 |              |           |                   |      ✔️      |              |              |            |
| **[Cohere](./docs/cohere.md)**                       |      ✔️      |    ✔️     |        ✔️         |              |              |      ✔️      |     ✔️     |
| **[Voyage AI](./docs/voyageai.md)**                  |              |    ✔️     |                   |              |              |              |            |
| **[Huggingface (with LiteLLM)](./docs/litellm.md)**  |              |    ✔️     |                   |              |              |              |            |
| **[Mistral (with LiteLLM)](./docs/litellm.md)**      |              |    ✔️     |                   |              |              |              |            |
| **[Azure OpenAI (with LiteLLM)](./docs/litellm.md)** |              |    ✔️     |                   |              |              |              |            |
| **[AWS Bedrock (with LiteLLM)](./docs/litellm.md)**  |              |    ✔️     |                   |              |              |              |            |
| **[Vertex AI (with LiteLLM)](./docs/litellm.md)**    |              |    ✔️     |                   |              |              |              |            |

Some examples:
- Learn how to [moderate](/docs/moderate.md) content directly in the database using triggers and background jobs. 
- [load datasets directly from Hugging Face](/docs/load_dataset_from_huggingface.md) into your database.
- Leverage LLMs for data processing tasks such as classification, summarization, and data enrichment ([see the OpenAI example](/docs/openai.md)).

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
[just]: https://github.com/casey/just
