
<p></p>
<div align=center>

# pgai

<h3>pgai brings AI workflows to your PostgreSQL database</h3>

[![Discord](https://img.shields.io/badge/Join_us_on_Discord-black?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/QedVDxRb)
[![Try Timescale for free](https://img.shields.io/badge/Try_Timescale_for_free-black?style=for-the-badge&logo=timescale&logoColor=white)](https://tsdb.co/gh-pgai-signup)
</div>

pgai simplifies the process of building [search](https://en.wikipedia.org/wiki/Similarity_search), and 
[Retrieval Augmented Generation](https://en.wikipedia.org/wiki/Prompt_engineering#Retrieval-augmented_generation)(RAG) AI applications with PostgreSQL. 

pgai brings embedding and generation AI models closer to the database. With pgai, you can now do the following directly from within PostgreSQL in a SQL query:

* Create [embeddings](#embed) for your data.
* Retrieve LLM [chat completions](#chat-complete) from models like OpenAI GPT4o and Llama 3.
* Generate responses for models such as Ollama.
* Reason over your data and facilitate use cases like [classification, summarization, and data enrichment](docs/advanced.md) on your existing relational data in PostgreSQL.

Here's how to get started with pgai:

* **Everyone**: Use pgai in your PostgreSQL database.
  1. [Set up pgai](#set-up-pgai).
  1. Use pgai to integrate AI from your provider:
    * [Ollama](./docs/ollama.md) - configure pgai with Ollama, then use the model to embed, chat complete and generate. 
    * [OpenAI](./docs/openai.md) - configure pgai with OpenAI, then use the model to tokenize, embed, chat complete and moderate. This page also includes advanced examples.
* **Extension contributor**: Contribute to pgai and improve the project.
  * [Develop and test changes to the pgai extension](./DEVELOPMENT.md).
  * See the [Issues tab](https://github.com/timescale/pgai/issues) for a list of feature ideas to contribute.

**Learn more about pgai:** To learn more about the pgai extension and why we built it, read this blog post [pgai: Giving PostgreSQL Developers AI Engineering Superpowers](http://www.timescale.com/blog/pgai-giving-postgresql-developers-ai-engineering-superpowers).

## Set up pgai

The fastest ways to run PostgreSQL with the pgai extension are to:

1. Create your Timescale environment. Either:
   * [Use a pre-built Docker container](#use-a-pre-built-docker-container).
   * [Install from source](#install-from-source).
   * [Use a Timescale Cloud service](#use-a-timescale-cloud-service).

2. [Enable the pgai extension](#enable-the-pgai-extension-in-your-database).

3. Use pgai to integrate AI from [Ollama](./docs/ollama.md) and [OpenAI](./docs/openai.md).

### Use a pre-built Docker container

[Run the TimescaleDB Docker image](https://docs.timescale.com/self-hosted/latest/install/installation-docker/).


### Install from source

You can install pgai from source in an existing PostgreSQL server.
You will need [Python3](https://www.python.org/downloads/) and [pip](https://pip.pypa.io/en/stable/) installed system-wide. 
You will also need to install the [plpython3](https://www.postgresql.org/docs/current/plpython.html) 
and [pgvector](https://github.com/pgvector/pgvector) extensions.
After installing these prerequisites, run:

```bash
make install
```

### Use a Timescale Cloud service

Create a new [Timescale Service](https://console.cloud.timescale.com/dashboard/create_services).

If you want to use an existing service, pgai is added as an available extension on the first maintenance window
after the pgai release date.

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

Now use pgai to integrate AI from [Ollama](./docs/ollama.md) and [OpenAI](./docs/openai.md).

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
