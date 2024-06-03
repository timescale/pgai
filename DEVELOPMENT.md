# Setup your pgai developer environment

This page shows you how to create your pgai developer environment. Best practice is to
[Setup a pgai environment in Docker](#setup-a-pgai-environment-in-docker). Timescale supplies the following pgai variants:

- To use pgai, either:
  - [Setup a pgai environment in Docker](#setup-a-pgai-environment-in-docker): this image
    includes all necessary software and extensions to use pgai.
  - [Integrate pgai into an existing PostgreSQL environment](#integrate-pgai-into-an-existing-postgresql-environment): add
    the pgai extension to your existing PostgreSQL and [pgvector][pgvector-install] environment.
- To develop pgai:
  - [Setup a virtual pgai environment](#setup-a-virtual-pgai-environment): create a virtual Ubuntu environment with 
    PostgreSQL installed.   
  - [Add pgai to your virtual or local developer environment](#setup-a-pgai-environment-locally): build pgai and pgvector from source and 
    add these extensions to your local or virtual PostgreSQL developer environment.  


When your environment is running, [Test your pgai environment](./README.md#test-your-pgai-environment).

## pgai Prerequisites

Before you start working with pgai, you need:

* An [OpenAI API Key](https://platform.openai.com/api-keys).
* [Psql](https://www.timescale.com/blog/how-to-install-psql-on-mac-ubuntu-debian-windows/) or [PopSQL](https://docs.timescale.com/use-timescale/latest/popsql/)
* The pgai source on your local machine:
   ```bash
   git clone git@github.com:timescale/pgai.git
   ```
* Docker environment:
    * [Docker](https://docs.docker.com/get-docker/)
* Virtual or local environment:
  * For a virtual Ubuntu environment:
      * [Multipass](https://multipass.run/)
  * For local development:
      *  [PostgreSQL](https://docs.timescale.com/self-hosted/latest/install/installation-linux/#install-and-configure-timescaledb-on-postgresql) v16
  * Build tools and PostgreSQL developer libraries:
     ```
     sudo apt-get install build-essential postgresql-server-dev-16
     ```

## Setup a pgai environment in Docker

The pgai Docker container has all the software you need preinstalled. To connect to
pgai running in a Docker container:


1. In Terminal, navigate to the folder you cloned this pgai repository to.

1. Build the Docker image:

   ```bash
   docker build -t pgai .
   ```

1. Run the container:

    ```bash
    docker run -d --name pgai -p 9876:5432 -e POSTGRES_PASSWORD=pgaipass --mount type=bind,src=`pwd`,dst=/pgai pgai
    ```
   You are automatically connected to the container. To connect from the command line, run
   `docker exec -it pgai /bin/bash`.

1. Connect to the database:

    ```bash
    psql -d "postgres://postgres:pgaipass@localhost:9876/postgres"
    ```

1. Create the pgai extension:

    ```sql
    CREATE EXTENSION ai CASCADE;
    ```
   The `CASCADE` automatically installs the plpython3u and pgvector dependencies.
1. You can now [Securely connect to your AI provider through pgai](./README.md#securely-connect-to-your-ai-provider-through-pgai).

If you make changes to this extension in `ai*.sql`, use the following command to upload
your new functionality to the Docker container:

```bash
docker exec pgai /bin/bash -c 'cp /pgai/ai* `pg_config --sharedir`/extension/'
```

This command copies the sources from the repo directory on the bind mount to
the postgres extensions directory.

## Integrate pgai into an existing PostgreSQL environment

pgai is a PostgreSQL extension written in SQL. Database functions are written in
plpython3u. There is no compilation required, simply integrate pgai into your
[PostgreSQL v16](https://docs.timescale.com/self-hosted/latest/install/installation-linux/#install-and-configure-timescaledb-on-postgresql) with
[pgvector][pgvector-install] environment.

1. In Terminal, navigate to the folder you cloned this pgai repository to.

1. Copy the pgai sql sources to the `postgresql-py` shared directory:

    ```bash
    cp ai* `pg_config --sharedir`/extension/
    ```

1. Connect to PostgreSQL:

   ```bash
   psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>"
   ```

1. Add pgai to a database:

    ```sql
    drop extension if exists ai
    create extension ai cascade
    ```
1. You can now [Securely connect to your AI provider through pgai](./README.md#securely-connect-to-your-ai-provider-through-pgai).

If you want to check that all is well, [Test your pgai environment](./README.md#test-your-pgai-environment).


## Setup a virtual pgai environment

Best practice is to setup your developer environment in Docker. However, to install pgai in a virtual
Ubunto environment.

In this repository, [vm.sh](./vm.sh) creates a [multipass](https://multipass.run/) virtual machine called `pgai`. This script
installs the [pgai Prerequisites](#pgai-prerequisites) in the `pgai` Ubuntu virtual
machine. This repo is mounted to `/pgai` in the virtual machine.

1. To create the virtual machine, run the following command:

    ```bash
    ./vm.sh
    ```

   You are automatically logged into Terminal as `ubuntu` on the virtual machine. 
   In multipass, this pgai repo is mounted on `/pgai`. To connect to 
   multipass from the command line, run `multipass shell pgai`

1. Login to PostgreSQL as postgres:

    ```bash
    sudo -u postgres psql
    ```
    You are in the psql shell.

1. **Set the password for `postgres`**

    ```bash
    \password postgres
    ```

   When you have set the password, type `\q` to exit psql.

You are ready to [Add pgai to your virtual or local developer environment](#add-pgai-to-your-virtual-or-local-developer-environment).

For more information on using Multipass, [see the documentation](https://multipass.run/docs/use-an-instance).

## Add pgai to your virtual or local developer environment

Best practice is to setup your developer environment in Docker. However, to integrate pgai into your
local or virtual developer environment:

1. In Terminal, navigate to the folder you cloned pgai to.

1. Build and install pgvector, pgai and python extensions on your PostgreSQL developer
   environment.

    ```bash
    make install
    ```

1. Create the pgai extension in a database. Use either:

    - psql:
        1. Connect to PostgreSQL:
           ```bash
           psql -d "postgres://postgres:<password>@localhost/postgres"
           ```

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
1. You can now [Securely connect to your AI provider through pgai](./README.md#securely-connect-to-your-ai-provider-through-pgai).



[pgvector-install]: https://github.com/pgvector/pgvector

