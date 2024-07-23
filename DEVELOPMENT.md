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
* [Python3](https://www.python.org/downloads/)
* [Docker](https://docs.docker.com/get-docker/)
* You will need API Keys for the LLM cloud providers you are working with (OpenAI, Anthropic, Cohere, etc.)
* If you will be working with Ollama, you will need it [running somewhere accessible](https://github.com/ollama/ollama/blob/main/README.md#quickstart).
  * [pull](https://github.com/ollama/ollama/blob/main/README.md#pull-a-model) the `llama3` model
  * [pull](https://github.com/ollama/ollama/blob/main/README.md#pull-a-model) the `llava:7b` model
* You may want a Postgres client on your host machine like [Psql](https://www.timescale.com/blog/how-to-install-psql-on-mac-ubuntu-debian-windows/) or [PopSQL](https://docs.timescale.com/use-timescale/latest/popsql/)

## The pgai development workflow

1. Clone the pgai repo
2. Navigate to the folder you cloned this pgai repository to
3. Build the docker image

   ```bash
   make docker-build
   ``

4. Run the container:

   ```bash
   make docker-run
   ```
   The repo directory is mounted to `/pgai` in the running container.

5. To get a shell inside the container, run

   ```bash
   make docker-shell
   ```
   You are logged in as root.

   1. Once you are in a shell in the container, install the extension

      ```bash
      make install
      ```

   2. Run the unit tests

      ```bash
      make test
      ```

6. To get a psql shell to the database in the docker container:

   ```bash
   make psql-shell
   ```

7. Later, to stop and delete the container, run:

   ```bash
   make docker-stop
   ```

   ```bash
   make docker-rm
   ```

## Test pgai

The [tests](./tests) directory contains unit tests in psql scripts. The
[test.sql](./tests/test.sql) script drives test runs.

1. Create a .env file in the root of the repo to store environment variables needed for testing:
   - ENABLE_OPENAI_TESTS - a [boolean](https://www.postgresql.org/docs/current/app-psql.html#PSQL-METACOMMAND-IF) flag to enable/disable OpenAI unit tests
   - ENABLE_OLLAMA_TESTS - a [boolean](https://www.postgresql.org/docs/current/app-psql.html#PSQL-METACOMMAND-IF) flag to enable/disable Ollama unit tests
   - ENABLE_ANTHROPIC_TESTS - a [boolean](https://www.postgresql.org/docs/current/app-psql.html#PSQL-METACOMMAND-IF) flag to enable/disable Anthropic unit tests
   - ENABLE_COHERE_TESTS - a [boolean](https://www.postgresql.org/docs/current/app-psql.html#PSQL-METACOMMAND-IF) flag to enable/disable Cohere unit tests
   - OPENAI_API_KEY - an [OpenAI API Key](https://platform.openai.com/api-keys) to use for OpenAI unit testing
   - OLLAMA_HOST - the URL to the Ollama instance to use for testing (e.g. `http://host.docker.internal:11434`)
   - ANTHROPIC_API_KEY - an [Anthropic API Key](https://docs.anthropic.com/en/docs/quickstart#set-your-api-key) to use for Anthropic unit testing
   - COHERE_API_KEY - a [Cohere API Key](https://docs.cohere.com/docs/rate-limits) to use for Cohere unit testing

2. If you have made changes to the source, from a docker shell, (re)install the extension

   ```bash
   make install
   ```

3. Run the tests

   ```bash
   make test
   ```

   This will:
   1. drop the "test" database if it exists
   2. create a "test" database
   3. create a database user named "tester" if it doesn't exist
   4. run [test.sql](./tests/test.sql) to execute the unit tests against the "test" database

Best practice is to add new tests when you commit new functionality.

## pgai Architecture

The pgai extension consists of SQL files as well as Python packages. SQL files 
are maintained in the [./sql](./sql) directory. The Python packages are 
maintained in the [./src](./src) directory.

### SQL

The SQL consists of both idempotent and incremental scripts. The code in 
[./sql/idempotent](./sql/idempotent) is executed on EVERY install AND upgrade of
the pgai extension and thus must be written with this in mind. Idempotent files
are executed in alphanumeric order of the file names. In general, it is safe to 
reorder these from one version to the next. Typically, idempotent files consist
of `CREATE OR REPLACE`-style statements (usually functions).

The code in [./sql/incremental](./sql/incremental) is guaranteed to execute 
exactly ONCE in the form of a database migration. Each file in the incremental 
directory is a migration - a separate unit-of-work that either succeeds or 
fails. Each incremental file is [wrapped](./sql/migration.sql) to facilitate the
migration. These migrations are tracked in a table named "ai_migration" 
(see [./sql/head.sql](./sql/head.sql) for details). Incremental files
are executed in alphnumeric order of the file names. It is not safe to reorder 
incremental files once they have been published as a part of a release. 
Typically, incremental files create tables and other stateful-structures that 
should not be dropped from one version upgrade to another.

The `make build-sql` "compiles" all of these scripts into the `ai--*.sql` files
in the [./sql](./sql) directory. These are the files that are actually installed
into postgres as an extension via `make install-sql`. The `make clean-sql` 
command will delete the `ai--*.sql` files in the [./sql](./sql) directory for 
the current version. When releasing a new version, the `ai--*.sql` files for the
current version need to be added to git and not modified thereafter.

### Python

Python code used by the pgai extension is maintained in the [./src](./src)
directory.

In order to support multiple versions of the extension being 
installed and upgraded from/to in a given postgres installation, we have to 
install every version of our python code and its associated dependencies. Each 
version of the Python code is installed under `/usr/local/lib/pgai/<version>`.

The `make install-py` command will compile and install the current version of 
the python package with it's associated dependencies to the target directory.

The `make install-prior-py` command will `git clone` the prior versions and
compile and install those versions with associated dependencies to the target
directory.

The `make uninstall-py` command deletes `/usr/local/lib/pgai`.

The `make clean-py` command removes the build artifacts from the repo directory.

The SQL functions add the appropriate path dynamically when looking to
import modules using [site.addsitedir()](https://docs.python.org/3/library/site.html#site.addsitedir)

#### Versions prior to 0.4.0

Versions prior to 0.4.0 installed Python dependencies into a system-wide 
location. We have moved away from that practice for version 0.4.0 and following.
Until we deprecate versions prior to 0.4.0 we need to continue installing the
old dependencies into the system-wide location. These old dependencies are
identified in [./src/old_requirements.txt](./src/old_requirements.txt).

