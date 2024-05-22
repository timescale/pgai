# Postgres AI

Postgres AI (PgAI) enables you to handle more AI workflows within a database. PgAI simplifies 
the process of building [similarity search](https://en.wikipedia.org/wiki/Similarity_search), and 
[Retrieval Augmented Generation](https://en.wikipedia.org/wiki/Prompt_engineering#Retrieval-augmented_generation) 
(RAG) apps with PostgreSQL. 

Directly from your existing PostgreSQL database, PgAI empowers you to:

* Create OpenAI [embeddings](https://platform.openai.com/docs/guides/embeddings). 
* Retrieve OpenAI [chat completions](https://platform.openai.com/docs/guides/text-generation/chat-completions-api) from 
  models such as GPT4o.
* Facilitate use cases such as classification, summarization, and data enrichment on your existing relational data.

This page shows you how to setup your environment in Docker or locally, and create your first AI models:

## Prerequisites

* The PgAI source on your developer environment:
   ```bash
   git clone git@github.com:timescale/pgai.git
   ```
* If you are using [Docker](#setup-your-developer-environment-in-docker):
  * [Docker](https://docs.docker.com/get-docker/)
* If you prefer [local development](#setup-your-developer-environment-locally):
  *  [PostgreSQL with pgvector](https://docs.timescale.com/self-hosted/latest/install/installation-linux/#install-and-configure-timescaledb-on-postgresql) v16
  *  [plpython3u](https://www.postgresql.org/docs/current/plpython.html)
  *  [Python3](https://www.python.org/downloads/) with the following packages:
     * [openai](https://pypi.org/project/openai/)
     * [tiktoken](https://pypi.org/project/tiktoken/)
   
## Setup your developer environment in Docker

1. On the command line, navigate to the folder you cloned PgAI to. 

1. Build the Docker image

   ```bash
   docker build -t pgai .
   ```

1. Run the container

    ```bash
    docker run -d --name pgai -p 9876:5432 -e POSTGRES_PASSWORD=pgaipass pgai
    ```

1. Connect to the database

    ```bash
    psql -d "postgres://postgres:pgaipass@localhost:9876/postgres"
    ```

1. Create the extension

    ```sql
    CREATE EXTENSION ai CASCADE;
    ```

## Setup your developer environment locally

Using docker is recommended, however a Makefile is provided if you wish to 
install the extension on your system. The `install` make target will download 
and install the pgvector extension, install the pgai extension, and install 
the Python package dependencies in your system's Python environment.

```bash
make install
```

## Create Extension

After installation, the extension must be created in a Postgres database. Since
the extension depends on both plpython3u and pgvector, using the `CASCADE` 
option is recommended to automatically install them if they are not already.

```sql
CREATE EXTENSION IF NOT EXISTS ai CASCADE;
```

Alternately, you can use the `create_extension` make target. Be aware that the
`DB` and `USER` make variables are used to establish a connection to the 
running database, so modify them accordingly if needed.

```bash
make create_extension
```

## Development

The `vm.sh` shell script will create a virtual machine named `pgai` using 
[multipass](https://multipass.run/) for development use. The repo director will
be mounted to `/pgai` in the virtual machine.

### Create the virtual machine

```bash
./vm.sh
```

### Get a shell in the virtual machine

```bash
multipass shell pgai
```

### Delete the virtual machine

```bash
multipass delete --purge pgai
```