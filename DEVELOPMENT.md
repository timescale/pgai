# Setup your pgai developer environment

Want to contribute to the pgai project? This page shows you how to create your pgai developer environment. Best practice is to
[Setup a pgai environment in Docker](#setup-a-pgai-environment-in-docker). 

This page shows you how to:

- [Setup a pgai environment in Docker](#setup-a-pgai-environment-in-docker): all necessary software and extensions to 
  develop pgai in a container.
- [Setup a virtual pgai environment](#setup-a-pgai-environment-in-a-virtual-machine): all necessary software and extensions to 
  develop pgai in a virtual Ubuntu environment.
- [Make changes to pgai](#make-changes-to-pgai): edit the pgai source and reflect the changes in the database
- [Test your pgai changes](#test-your-pgai-changes): use the tests.sql script to test your pgai changes.

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

2. Build the Docker image:

   ```bash
   make docker_build
   ```

3. Run the container:

   ```bash
   make docker_run
   ```
   The repo directory is mounted to `/pgai` in the running container.

4. To get a shell inside the container, run
   
   ```bash
   make docker_shell
   ```
   You are logged in as root.

5. Connect to the database:

   To connect from outside the container:
   ```bash
   psql -d "postgres://postgres:pgaipass@localhost:9876/postgres"
   ```
   To connect from a shell within the container:
   ```bash
   su postgres -
   psql
   ```

6. Later, to stop and delete the container, run:
   
   ```bash
   make docker_stop
   ```
   
   ```bash
   make docker_rm
   ```

## Setup a pgai environment in a virtual machine

Best practice is to setup your developer environment in Docker. However, to install pgai in a virtual
Ubuntu environment using multipass.

1. To create the virtual machine, run the following command:

   ```bash
   make vm_create
   ```

   - The virtual machine is started, and you are automatically logged into a shell as `ubuntu` on the virtual machine.
   - The repo directory is mounted to `/pgai` in the virtual machine.

2. Login to PostgreSQL from within the virtual machine:

   As the ubuntu database user:
   ```bash
   psql
   ```
   You are in the psql shell.

3. Later, to stop, start, get a shell inside the vm, and delete the vm, run:

   ```bash
   make vm_stop
   ```

   ```bash
   make vm_start
   ```

   ```bash
   make vm_shell
   ```

   ```bash
   make vm_delete
   ```

For more information on using Multipass, [see the documentation](https://multipass.run/docs/use-an-instance).


## Make changes to pgai

The repo is mounted to `/pgai` in the docker container/virtual machine. You 
may edit the source from either inside the docker container/virtual machine
or from the host machine.

If you have updated the [unit tests](./tests.sql) accordingly, you may simply 
[test your changes](#test-your-pgai-changes), or you can manually update the 
database with your changes.

To reflect your changes in the database manually, do the following from within 
the docker container/virtual machine.

1. Copy the edited sources to the appropriate postgres directory:
   ```bash
   make install_extension
   ```
2. From a psql session, run:
   ```bash
   DROP EXTENSION IF EXISTS ai CASCADE;
   CREATE EXTENSION ai CASCADE;
   ```

## Test your pgai changes

[tests.sql](./tests.sql) contains unit tests to validate your changes. 
From within the docker container/virtual machine:

1. Make sure your OpenAI API key is in your shell's environment

   ```bash
   export OPENAI_API_KEY="<your key here>"
   ```

2. Run the tests

   ```bash
   make test
   ```

   This will:
   1. copy the sources from the `/pgai` directory to the correct postgres directory
   2. drop the "test" database if it exists
   3. create a "test" database
   4. run [tests.sql](./tests.sql) in the "test" database

Best practice is to add new tests when you commit new functionality.
