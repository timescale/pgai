# Setup your pgai developer environment

This page shows you how to create your pgai developer environment. Best practice is to
[Setup a pgai environment in Docker](#setup-a-pgai-environment-in-docker). Timescale supplies the following pgai variants:

- [Integrate pgai into an existing PostgreSQL environment](#integrate-pgai-into-an-existing-postgresql-environment) 
- [Setup a pgai environment in Docker](#setup-a-pgai-environment-in-docker)
- [Setup a virtual pgai environment](#setup-a-virtual-pgai-environment)
- [Setup a local pgai environment](#setup-a-pgai-environment-locally)

When your environment is running, [Test your pgai environment](#test-your-pgai-environment).

## pgai Prerequisites

Before you start working with pgai, you need:

* An [OpenAI API Key](https://platform.openai.com/api-keys).
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

## Integrate pgai into an existing PostgreSQL environment

pgai is a PostgreSQL extension written in SQL. Database functions are written in
plpython3u. There is no compilation required, simply integrate pgai into your
[PostgreSQL with pgvector](https://docs.timescale.com/self-hosted/latest/install/installation-linux/#install-and-configure-timescaledb-on-postgresql) environment.

1. In Terminal, navigate to the folder you cloned this pgai repository to.

1. Copy the pgai sql sources to the `postgresql-py` shared directory:

    ```bash
    cp ai* `pg_config --sharedir`/extension/
    ```

1. Connect to PostgreSQL:

   ```bash
   psql -d "your://postgres:configuration@string:9876/database-name"
   
   ```

1. Add pgai to a database from the source you just installed.

    ```sql
    drop extension if exists ai;
    create extension ai cascade;
    ```

If you want to check that all is well, [Test your pgai environment](./DEVELOPMENT.md#test-your-pgai-environment).

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

If you make changes to this extension in `ai*.sql`, use the following command to upload
your new functionality to the Docker container:

```bash
docker exec pgai /bin/bash -c 'cp /pgai/ai* `pg_config --sharedir`/extension/'
```

This command copies the sources from the repo directory on the bind mount to
the postgres extensions directory.

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

   You are automatically logged into Terminal on the virtual machine.

1. In the multipass shell, [Setup a developer environment locally](#setup-a-developer-environment-locally).

For more information on using Multipass, [see the documentation](https://multipass.run/docs/use-an-instance).

## Setup a pgai environment locally

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



## Test your pgai environment

`tests.sql` contains unit tests to validate your environment. To run the tests:

- Terminal
    ```bash
    psql -v OPENAI_API_KEY=$OPENAI_API_KEY -f tests.sql
    ```

- psql session
    
    ```sql
    \i tests.sql
    ```

Best practice is to add new tests when you commit new functionality.

