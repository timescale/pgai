# Setup your pgai developer environment

Want to contribute to the pgai project? This page shows you how to create your pgai developer environment. Best practice is to
[Setup a pgai environment in Docker](#setup-a-pgai-environment-in-docker). 

This page shows you how to:

- [Setup a pgai environment in Docker](#setup-a-pgai-environment-in-docker): all necessary software and extensions to 
  develop pgai in a container.
- [Setup a virtual pgai environment](#setup-a-virtual-pgai-environment): all necessary software and extensions to 
  develop pgai in a virtual Ubuntu environment.   
- [Test your pgai changes](#test-your-pgai-changes): use the tests.sql script to validate your pgai environment.

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

The pgai Docker container has all the software you need preinstalled. To build and run the
pgai Docker container, then connect to it:


1. Navigate to the folder you cloned this pgai repository to.

1. Build the Docker image:

   ```bash
   make docker_build
   ```

1. Run the container:

   ```bash
   make docker_run
   ```
   Later, to stop and delete the container, run:
   ```bash
   make docker_delete
   ```

1. To get a shell inside the container, run
   
   ```bash
   make docker_shell
   ```

1. Connect to the database:

   To connect from outside the container:
   ```bash
   psql -d "postgres://postgres:pgaipass@localhost:9876/postgres"
   ```
   To connect from a shell within the container:
   ```bash
   su postgres -
   psql
   ```

1. Create the pgai extension:

    ```sql
    CREATE EXTENSION ai CASCADE;
    ```
   The `CASCADE` automatically installs the plpython3u and pgvector dependencies.

1. To update the database with your changes:

   If you make changes to this extension in `ai*.sql`, use the following command to upload
   your new functionality to the Docker container from outside the container:
   
   ```bash
   docker exec pgai /bin/bash -c 'cd /pgai && make install_extension'
   ```
   or from within the container:
   ```bash
   cd /pgai
   make install_extension
   ```

   These commands copy the sources from the repo directory on the bind mount to
   the postgres extensions directory.

   Then, from within a psql session, recreate the extension with:
   ```bash
   DROP EXTENSION ai CASCADE;
   CREATE EXTENSION ai CASCADE;
   ```

## Setup a pgai environment in a virtual machine

Best practice is to setup your developer environment in Docker. However, to install pgai in a virtual
Ubuntu environment using multipass.

In this repository, [vm.sh](./vm.sh) creates a [multipass](https://multipass.run/) virtual machine called `pgai`. This script
installs all the software you need in the `pgai` Ubuntu virtual
machine. This repo is mounted to `/pgai` in the virtual machine.

1. To create the virtual machine, run the following command:

   ```bash
   make vm_create
   ```

   The virtual machine is started, and you are automatically logged into a shell as `ubuntu` on the virtual machine. 

1. To start, stop and delete the virtual machine, run:

   ```bash
   make vm_start
   ```

   ```bash
   make vm_stop
   ```

   ```bash
   make vm_delete
   ```

1. To get a shell inside the virtual machine, run:

   ```bash
   make vm_shell
   ```
   For more information on using Multipass, [see the documentation](https://multipass.run/docs/use-an-instance).

1. Login to PostgreSQL from within the virtual machine:

   As the postgres database user:
   ```bash
   sudo -u postgres psql
   ```
   As the ubuntu database user:
   ```bash
   psql
   ```
   You are in the psql shell.

1. Login to PostgreSQL from outside the virtual machine:
   
   First, connect to postgres from within the virtual machine, and then set the password for `postgres`. 
   ```bash
   \password postgres
   ```

   When you have set the password, type `\q` to exit psql.

   Then, from outside the virtual machine, run:
   ```bash
   psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>"
   ```

1. Build and install pgvector, pgai and the python extensions on your PostgreSQL developer
   environment.

    From inside the virtual machine, run:
    ```bash
    cd /pgai
    make install
    ```

1. Create the pgai extension in a database. Use either:

    - psql:
        1. Connect to PostgreSQL using one of the options above.

        1. Create the pgai extension:

            ```sql
            CREATE EXTENSION IF NOT EXISTS ai CASCADE;
            ```

           The `CASCADE` automatically installs the plpython3u and pgvector dependencies.

    - Terminal:
        1. In `Makefile`, update `DB` and `USER` to match your PostgreSQL configuration.
        1. From a shell inside the virtual machine, create the pgai extension:

           ```bash
           cd /pgai
           make create_extension
           ```

1. To update the database with your changes:

    1. To copy your changes to the appropriate directories, run this from within the virtual machine:
       ```bash
       cd /pgai
       make install_extension
       ```
    1. Then, from within a psql session, recreate the extension with:
       ```bash
       DROP EXTENSION ai CASCADE;
       CREATE EXTENSION ai CASCADE;
       ```

## Test your pgai changes

`tests.sql` contains unit tests to validate your changes. To run the tests:

- Terminal
    ```bash
    psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>" -v OPENAI_API_KEY=$OPENAI_API_KEY -f tests.sql
    ```

- psql session

    ```sql
    \i tests.sql
    ```

Best practice is to add new tests when you commit new functionality.


