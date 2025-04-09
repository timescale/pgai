
<p align="center">
    <img height="200" src="/docs/images/pgai_logo.png#gh-dark-mode-only" alt="pgai"/>
    <img height="200" src="/docs/images/pgai_white.png#gh-light-mode-only" alt="pgai"/>
</p>

<div align=center>

<h3>Power your AI applications with PostgreSQL</h3>

<div>
  <a href="https://github.com/timescale/pgai/tree/main/docs"><strong>Docs</strong></a> ·
  <a href="https://discord.gg/KRdHVXAmkp"><strong>Join the pgai Discord!</strong></a> ·
  <a href="https://tsdb.co/gh-pgai-signup"><strong>Try timescale for free!</strong></a> ·
  <a href="https://github.com/timescale/pgai/releases"><strong>Changelog</strong></a>
</div>
</div>
<br/>

Use a PostgreSQL extension to make it easier to access AI features from within the database.
Supports:  

- Ability to call out to leading LLMs like OpenAI, Ollama, Cohere, and more via SQL.
- Built-in utilities for dataset loading and processing 
- Retrieval Augmented Generation (RAG) directly in SQL


### Docker

See the [install via docker](docs/install/docker.md) guide for docker compose files and detailed container instructions.

### Timescale Cloud

Try pgai on cloud by creating a [free trial account](https://tsdb.co/gh-pgai-signup) on Timescale Cloud. 


### Installing pgai into an existing PostgreSQL instance (Linux / MacOS)

See the [install from source](docs/install/source.md) guide for instructions on how to install pgai from source.                  

# Quick Start

This section will walk you through the steps to get started with pgai and Ollama using docker and show you the major features of pgai. 

Please note that using Ollama requires a large (>4GB) download of the docker image and model. If you don't want to download so much data, you may want to use the [OpenAI quick start](/docs/vectorizer/quick-start-openai.md) or [VoyageAI quick start](/docs/vectorizer/quick-start-voyage.md) instead.

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
    
    First, we'll create the table:

    ```sql
    CREATE TABLE wiki (
        id      TEXT PRIMARY KEY,
        url     TEXT,
        title   TEXT,
        text    TEXT
    );
    ```

    Then, we'll load the data from the huggingface dataset:

    ```sql
    SELECT ai.load_dataset('wikimedia/wikipedia', '20231101.en', table_name=>'wiki', batch_size=>5, max_batches=>1, if_table_exists=>'append');
    ```
    
    Related documentation: [load dataset from huggingface](/docs/utils/load_dataset_from_huggingface.md).

1. **Generate a summary of the article in the database**
    
    We'll generate a summary of the search results using the `ai.ollama_generate` function (this will take a few minutes).

    ```sql
    SELECT answer->>'response' as summary
    FROM ai.ollama_generate('tinyllama', 
    'Summarize the following and output the summary in a single sentence: '|| (SELECT text FROM wiki WHERE title like 'pgai%')) as answer;
    ```

    <details>
    <summary>Click to see the output</summary>

    | summary |
    |--------------------------------|
    | Pgai is a tool that simplifies the process of making AI applications easier by providing easy access to data in PostgreSQL and enabling semantic search on the data for the Retrieval Augmented Generation (RAG) pipeline. This allows the AI system to answer questions about unseen data without being trained on it, simplifying the entire process. |
    </details>
    

    This is just one example of [model calling capabilities](#model-calling). Model calling can be used for a variety of tasks, including classification, summarization, moderation, and other forms of data enrichment. 
    
# Features 

## Leverage LLMs for data processing tasks
* Retrieve LLM chat completions from models like Claude Sonnet 3.5, OpenAI GPT4o, Cohere Command, and Llama 3 (via Ollama). ([learn more](#usage-of-pgai))
* Reason over your data and facilitate use cases like classification, summarization, and data enrichment on your existing relational data in PostgreSQL ([see an example](/docs/model_calling/openai.md)).

## Useful utilities
* Load datasets from Hugging Face into your database with [ai.load_dataset](/docs/utils/load_dataset_from_huggingface.md).
* Use chunking algorithms to split text with [SQL functions](/docs/utils/chunking.md).

# Resources
## Why we built it
- [pgai: Giving PostgreSQL Developers AI Engineering Superpowers](http://www.timescale.com/blog/pgai-giving-postgresql-developers-ai-engineering-superpowers)

## Tutorials about pgai model calling
- [In-Database AI Agents: Teaching Claude to Use Tools With Pgai](https://www.timescale.com/blog/in-database-ai-agents-teaching-claude-to-use-tools-with-pgai/)
- [Build Search and RAG Systems on PostgreSQL Using Cohere and Pgai](https://www.timescale.com/blog/build-search-and-rag-systems-on-postgresql-using-cohere-and-pgai/)
- [Use Open-Source LLMs in PostgreSQL With Ollama and Pgai](https://www.timescale.com/blog/use-open-source-llms-in-postgresql-with-ollama-and-pgai/)

### Search your data using vector and semantic search

The pgai extension exposes a set of functions to directly interact with the LLM models through SQL, enabling
you to do semantic search directly in your database:

```sql
SELECT
   chunk,
   embedding <=> ai.ollama_embed(<embedding_model>, 'some-query') as distance
FROM <embedding_table>
ORDER BY distance
LIMIT 5;
```

### Implement Retrieval Augmented Generation inside a single SQL statement

pgai LLM functions enable you to implement RAG directly in your database. For example, 
if you have a table called `blog_embeddings` that has chunked, embedded data for your blogs,
you can use the following code to perform RAG:

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
| **[Ollama](docs/model_calling/ollama.md)**                       |              |    ✔️     |        ✔️         |      ✔️      |              |              |            |
| **[OpenAI](docs/model_calling/openai.md)**                       |     ✔️️      |    ✔️     |        ✔️         |              |      ✔️      |              |            |
| **[Anthropic](docs/model_calling/anthropic.md)**                 |              |           |                   |      ✔️      |              |              |            |
| **[Cohere](docs/model_calling/cohere.md)**                       |      ✔️      |    ✔️     |        ✔️         |              |              |      ✔️      |     ✔️     |
| **[Voyage AI](docs/model_calling/voyageai.md)**                  |              |    ✔️     |                   |              |              |              |            |
| **[Huggingface (with LiteLLM)](docs/model_calling/litellm.md)**  |              |    ✔️     |                   |              |              |              |            |
| **[Mistral (with LiteLLM)](docs/model_calling/litellm.md)**      |              |    ✔️     |                   |              |              |              |            |
| **[Azure OpenAI (with LiteLLM)](docs/model_calling/litellm.md)** |              |    ✔️     |                   |              |              |              |            |
| **[AWS Bedrock (with LiteLLM)](docs/model_calling/litellm.md)**  |              |    ✔️     |                   |              |              |              |            |
| **[Vertex AI (with LiteLLM)](docs/model_calling/litellm.md)**    |              |    ✔️     |                   |              |              |              |            |

Some examples:
- Learn how to [moderate](docs/model_calling/moderate.md) content directly in the database using triggers and background jobs. 
- [load datasets directly from Hugging Face](docs/utils/load_dataset_from_huggingface.md) into your database.
- Leverage LLMs for data processing tasks such as classification, summarization, and data enrichment ([see the OpenAI example](docs/model_calling/openai.md)).

## Get involved

pgai is still at an early stage. Now is a great time to help shape the direction of this project;
we are currently deciding priorities. Have a look at the [list of features](https://github.com/timescale/pgai/issues) we're thinking of working on.
Feel free to comment, expand the list, or hop on the Discussions forum.

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
