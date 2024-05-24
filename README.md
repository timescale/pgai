# Postgres AI

Postgres AI (pgai) enables you to handle more AI workflows within a database. pgai simplifies 
the process of building [similarity search](https://en.wikipedia.org/wiki/Similarity_search), and 
[Retrieval Augmented Generation](https://en.wikipedia.org/wiki/Prompt_engineering#Retrieval-augmented_generation) 
(RAG) apps with PostgreSQL. 

Directly from your existing PostgreSQL database, pgai empowers you to:

* Create OpenAI [embeddings](https://platform.openai.com/docs/guides/embeddings). 
* Retrieve OpenAI [chat completions](https://platform.openai.com/docs/guides/text-generation/chat-completions-api) from 
  models such as GPT4o.
* Facilitate use cases such as classification, summarization, and data enrichment on your existing relational data.

This page shows you how to setup your developer environment, then create your first AI models:

## pgai Prerequisites

Before you start working with pgai, you need:

* The pgai source on your local machine:
   ```bash
   git clone git@github.com:timescale/pgai.git
   ```
* If you prefer using Docker:
  * [Docker](https://docs.docker.com/get-docker/)
  * [Psql](https://www.timescale.com/blog/how-to-install-psql-on-mac-ubuntu-debian-windows/) or [PopSQL](https://docs.timescale.com/use-timescale/latest/popsql/)
* If you prefer a local virtual Ubuntu environment:
    * [Multipass](https://multipass.run/)
* If you prefer local development:
  *  [PostgreSQL with pgvector](https://docs.timescale.com/self-hosted/latest/install/installation-linux/#install-and-configure-timescaledb-on-postgresql) v16
     TODO: this package does not include `pgxs.mk`. Can you update the install instructions please. 
  *  [plpython3u](https://www.postgresql.org/docs/current/plpython.html)
  *  [Python3](https://www.python.org/downloads/)

## Setup your pgai developer environment

Best practice is to use the Docker environment supplied by Timescale. You can also integrate
pgai into your local developer environment. Either:

<details>
<summary>Setup a developer environment in Docker</summary>

The pgai Docker container has all the software you need preinstalled. To connect to
pgai running in a Docker container:


1. In Terminal, navigate to the folder you cloned pgai to. 

1. Build the Docker image:

   ```bash
   docker build -t pgai .
   ```

1. Run the container:

    ```bash
    docker run -d --name pgai -p 9876:5432 -e POSTGRES_PASSWORD=pgaipass pgai
    ```

1. Connect to the database:

    ```bash
    psql -d "postgres://postgres:pgaipass@localhost:9876/postgres"
    ```

1. Create the pgai extension:

    ```sql
    CREATE EXTENSION ai CASCADE;
    ```
   The `CASCADE` automatically installs the plpython3u and pgvector dependencies.

</details>
<details>
<summary>Setup a virtual developer environment locally</summary>

Best practice is to setup your developer environment in Docker. However, to install pgai in a virtual
Ubunto environment.

In this repository, [vm.sh](./vm.sh) creates a [multipass](https://multipass.run/) virtual machine called `pgai`. This script 
installs the [pgai Prerequisites](#pgai-prerequisites) in the `pgai` Ubuntu virtual
machine for you. This repo is mounted to `/pgai` in the virtual machine.

1. To create the virtual machine, run the following command:

    ```bash
    ./vm.sh
    ```

    You are automatically logged into a terminal on the virtual machine.

1. In the multipass shell, [Setup a developer environment locally](#setup-a-developer-environment-locally).

For more information on using Multipass, see [their documentation](https://multipass.run/docs/use-an-instance)

</details>
<details>
<summary>Setup a developer environment locally</summary>


Best practice is to setup your developer environment in Docker. However, to install pgai directly on your 
developer environment. 

1. On the command line, navigate to the folder you cloned pgai to.

1. Build pgai:

    ```bash
    make install
    ```

    This installs the pgvector and pgai extensions on your local PostgreSQL developer
    environment, then installs the package dependencies in your Python environment.

   
1. Create the pgai extension in a database. Use either:

   - SQL:
      1. Connect to PostgreSQL:
         ```bash
         psql -d "postgres://postgres:pgaipass@localhost:9876/postgres"
         ```
         TODO: Is this true for the local installation? Is the database already created?

      1. Create the pgai extension:
   
          ```sql
          CREATE EXTENSION IF NOT EXISTS ai CASCADE;
          ```
    
          The `CASCADE` automatically installs the plpython3u and pgvector dependencies.

   - Terminal: 
     1. In `Makefile`, update `DB` and `USER` to match your PostgreSQL configuration. 
     1.  Create the pgai extension:

        ```bash
        make create_extension
        ```
<details>
