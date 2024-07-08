# Develop and test changes to the pgai extension

Want to contribute to the pgai project? Start here.

This page shows you how to:

- [Set up a pgai development environment in Docker](#set-up-a-pgai-development-environment-in-docker): all necessary software and extensions to 
  develop pgai in a container.
- [Make changes to pgai](#make-changes-to-pgai): edit the pgai source and reflect the changes in the database
- [Test your pgai changes](#test-your-pgai-changes): use the tests.sql script to test your pgai changes.

## pgai Prerequisites

Before you start working with pgai, you need:

* The pgai source on your local machine:
   ```bash
   git clone git@github.com:timescale/pgai.git
   ```
* [Docker](https://docs.docker.com/get-docker/)
* If you will be working with OpenAI, you will need an [OpenAI API Key](https://platform.openai.com/api-keys).
* If you will be working with Ollama, you will need it [running somewhere accessible](https://github.com/ollama/ollama/blob/main/README.md#quickstart).
  * [pull](https://github.com/ollama/ollama/blob/main/README.md#pull-a-model) the `llama3` model
  * [pull](https://github.com/ollama/ollama/blob/main/README.md#pull-a-model) the `llava:7b` model
* You may want a Postgres client on your host machine like [Psql](https://www.timescale.com/blog/how-to-install-psql-on-mac-ubuntu-debian-windows/) or [PopSQL](https://docs.timescale.com/use-timescale/latest/popsql/)

## Set up a pgai development environment in Docker

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
   psql -d "postgres://postgres@localhost:9876/postgres"
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

## Make changes to pgai

The repo is mounted to `/pgai` in the docker container. You may edit the source 
from either inside the docker container or from the host machine.

If you have updated the [unit tests](./tests) accordingly, you may simply 
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

The [tests](./tests) directory contains unit tests in psql scripts. The 
[test.sql](./test.sql) script drives test runs.

1. Create a .env file to store environment variables needed for testing:
   - ENABLE_OPENAI_TESTS - a [boolean](https://www.postgresql.org/docs/current/app-psql.html#PSQL-METACOMMAND-IF) flag to enable/disable OpenAI unit tests
   - ENABLE_OLLAMA_TESTS - a [boolean](https://www.postgresql.org/docs/current/app-psql.html#PSQL-METACOMMAND-IF) flag to enable/disable Ollama unit tests
   - ENABLE_ANTHROPIC_TESTS - a [boolean](https://www.postgresql.org/docs/current/app-psql.html#PSQL-METACOMMAND-IF) flag to enable/disable Anthropic unit tests
   - ENABLE_COHERE_TESTS - a [boolean](https://www.postgresql.org/docs/current/app-psql.html#PSQL-METACOMMAND-IF) flag to enable/disable Cohere unit tests
   - OPENAI_API_KEY - an [OpenAI API Key](https://platform.openai.com/api-keys) to use for OpenAI unit testing
   - OLLAMA_HOST - the URL to the Ollama instance to use for testing (e.g. `http://host.docker.internal:11434`)
   - ANTHROPIC_API_KEY - an [Anthropic API Key](https://docs.anthropic.com/en/docs/quickstart#set-your-api-key) to use for Anthropic unit testing
   - COHERE_API_KEY - a [Cohere API Key](https://docs.cohere.com/docs/rate-limits) to use for Cohere unit testing

2. Run the tests

   ```bash
   make test
   ```

   This will:
   1. run `make install_extension` to copy the sources from the `/pgai` directory to the correct postgres directory
   2. drop the "test" database if it exists
   3. create a "test" database
   4. create a database user named "tester" if it doesn't exist
   5. run [test.sh](./test.sh) to execute the unit tests against the "test" database

Best practice is to add new tests when you commit new functionality.
