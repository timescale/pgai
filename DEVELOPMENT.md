# Setup your pgai developer environment

This page shows you how to create your pgai developer environment. Best practice is to
[Setup a pgai environment in Docker](#setup-a-pgai-environment-in-docker). 

This page shows you how to:

- [Setup a pgai environment in Docker](#setup-a-pgai-environment-in-docker): all necessary software and extensions to 
  develop pgai in a container.
- [Setup a virtual pgai environment](#setup-a-virtual-pgai-environment): all necessary software and extensions to 
  develop pgai in a virtual Ubuntu environment.   
- [Test your pgai environment](#test-your-pgai-environment): use the tests.sql script to validate your pgai environment.

## pgai Prerequisites

Before you start working with pgai, you need:

* An [OpenAI API Key](https://platform.openai.com/api-keys).
* [Psql](https://www.timescale.com/blog/how-to-install-psql-on-mac-ubuntu-debian-windows/) or [PopSQL](https://docs.timescale.com/use-timescale/latest/popsql/)
* The pgai source on your local machine:
   ```bash
   git clone git@github.com:timescale/pgai.git
   ```
* Your virtual environment, either:
    * [Docker](https://docs.docker.com/get-docker/)
    * [Multipass](https://multipass.run/)
    * Or both, why not :metal:? 

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
1. [Securely connect to your AI provider through pgai](./README.md#securely-connect-to-your-ai-provider-through-pgai).

If you make changes to this extension in `ai*.sql`, use the following command to upload
your new functionality to the Docker container:

```bash
docker exec pgai /bin/bash -c 'cp /pgai/ai* `pg_config --sharedir`/extension/'
```

This command copies the sources from the repo directory on the bind mount to
the postgres extensions directory.


## Setup a virtual pgai environment

Best practice is to setup your developer environment in Docker. However, to install pgai in a virtual
Ubuntu environment.

In this repository, [vm.sh](./vm.sh) creates a [multipass](https://multipass.run/) virtual machine called `pgai`. This script
installs the [pgai Prerequisites](#pgai-prerequisites) in the `pgai` Ubuntu virtual
machine. This repo is mounted to `/pgai` in the virtual machine.

1. To create the virtual machine, run the following command:

    ```bash
    ./vm.sh
    ```

   You are automatically logged into Terminal as `ubuntu` on the virtual machine. 
   
   To connect to multipass from the command line, run `multipass shell pgai`. For more information 
   on using Multipass, [see the documentation](https://multipass.run/docs/use-an-instance).

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

1. Build and install pgvector, pgai and the python extensions on your PostgreSQL developer
   environment.

    ```bash
    make install
    ```

1. Create the pgai extension in a database. Use either:

    - psql:
        1. Connect to PostgreSQL:
           ```bash
           psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>"
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


You can now [Securely connect to your AI provider through pgai](./README.md#securely-connect-to-your-ai-provider-through-pgai).

## Test your pgai environment

`tests.sql` contains unit tests to validate your environment. To run the tests:

- Terminal
    ```bash
    psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>" -v OPENAI_API_KEY=$OPENAI_API_KEY -f tests.sql
    ```

- psql session

    ```sql
    \i tests.sql
    ```

Best practice is to add new tests when you commit new functionality.


