# Develop and test changes to pgai

pgai brings embedding and generation AI models closer to the database. Want to contribute to the pgai project?
Start here. This page shows you:

- [The pgai development workflow](#the-pgai-development-workflow): build, run and test pgai in a Docker container.
- [How to test pgai](#test-pgai): use the psql script to test your changes to pgai.
- [The pgai build architecture](#the-pgai-build-architecture): work with multiple versions of pgai in the same environment.


## pgai Prerequisites

To make changes to the pgai extension, do the following in your developer environment:

* Install:
   * [Python3](https://www.python.org/downloads/).
   * [Docker](https://docs.docker.com/get-docker/).
   * A Postgres client like [Psql](https://www.timescale.com/blog/how-to-install-psql-on-mac-ubuntu-debian-windows/) or [PopSQL](https://docs.timescale.com/use-timescale/latest/popsql/).
* Retrieve the API Keys for the LLM cloud providers you are working with.
* Clone the pgai source:
   ```bash
   git clone git@github.com:timescale/pgai.git
   cd pgai
   ```
* Ollama only:
   * [Run Ollama somewhere accessible from your developer environment](https://github.com/ollama/ollama/blob/main/README.md#quickstart).
   * [Pull the `llama3` and  `llava:7b` models](https://github.com/ollama/ollama/blob/main/README.md#pull-a-model):
     ```shell
     ollama pull llama3
     ollama pull llava:7b
     ```

## The pgai development workflow

To make changes to pgai:

1. Navigate to `<pgai_source_dir>`.
1. Build the docker image
   ```bash
   make docker-build
   ```
4. Run the container:
   ```bash
   make docker-run
   ```
   The repo directory is mounted to `/pgai` in the running container.

5. Work inside the container:
   * **Docker shell**:
      1. Open get a shell session in the container:

         ```bash
         make docker-shell
         ```
         You are logged in as root.

      1. Install the extension

         ```bash
         make install
         ```

      2. Run the unit tests

         ```bash
         make test
         ```

   * **psql shell**:
      1. To get a psql shell to the database in the docker container:

         ```shell
         make psql-shell
         ```
      1. Make the changes you want using psql.

7. Stop and delete the container:

   ```shell
   # Stop the container
   make docker-stop
   # Delete the container
   make docker-rm
   ```


## Test pgai

The [tests](./tests) directory contains the psql scripts that run unit tests. The tests are driven by
[test.sql](./tests/test.sql).

To setup the pgai tests:

1. In `<pgai_source_dir>/.env`, add the variables for the framework you want to test:
   - **OpenAI**:
      - ENABLE_OPENAI_TESTS - set to `true` to enable OpenAI unit tests.
      - OPENAI_API_KEY - an [OpenAI API Key](https://platform.openai.com/api-keys) for OpenAI unit testing.
   - **Ollama**:
      - ENABLE_OLLAMA_TESTS - set to `true` to enable Ollama unit tests.
      - OLLAMA_HOST - the URL to the Ollama instance to use for testing. For example, `http://host.docker.internal:11434`.
   - **Anthropic**:
      - ENABLE_ANTHROPIC_TESTS - set to `true` to enable Anthropic unit tests.
      - ANTHROPIC_API_KEY - an [Anthropic API Key](https://docs.anthropic.com/en/docs/quickstart#set-your-api-key) for Anthropic unit testing.
   - **Cohere**:
      - ENABLE_COHERE_TESTS - set to `true` to enable Cohere unit tests.
      - COHERE_API_KEY - a [Cohere API Key](https://docs.cohere.com/docs/rate-limits) for Cohere unit testing.

2. If you have made changes to the source, from a Docker shell, install the extension:
   ```bash
   cd <pgai_source_dir>
   make docker-shell
   make install
   ```
   You are in a Docker shell.

3. Run the tests

   ```bash
   make test
   ```

   This:
   1. Drops the `test` database.
   2. Creates the `test` database.
   3. Creates the `tester` database user.
   4. Runs [test.sql](./tests/test.sql) which execute the unit tests against the `test` database.

Best practice is to add new tests when you commit new functionality.

## The pgai build architecture

pgai consists of [SQL](#sql) scripts and [Python](#python) packages.

The pgai build has the following paths:

* [Build everything as is](#build-everything-as-is): the default workflow. 
* [Build the SQL scripts in pgai](#build-the-sql-scripts-in-pgai): update sql migration scripts.
* [Build the Python code in pgai](#build-the-python-code-in-pgai): update functionality in pgai. 
* [Versions prior to 0.4.0](#versions-prior-to-040): the legacy installation procedure.

### Build everything as is

The installation workflow to build the SQL scripts and Python code in pgai is:

1. **Clean your environment**: run `make clean` to remove build artifacts from your developer 
   environment.
1. **Install pgai**:
   To compile and install pgai, run `make install`.
1. **Uninstall pgai**: run `make uninstall` and delete all versions of pgai from your developer
   environment. 



### Build the SQL scripts in pgai

SQL code used by pgai is maintained in [<pgai_source_dir>/sql](./sql).

The SQL is organized into:

* **Idempotent scripts**: maintained in [./sql/idempotent](./sql/idempotent).

  Idempotent scripts consist of `CREATE OR REPLACE` style statements, usually as
  functions. They are executed in alphanumeric order every time you install or
  upgrade pgai. In general, it is safe to rename these scripts from one version to
  the next.

* **Incremental scripts**: maintained in [./sql/incremental](./sql/incremental).

  Incremental files create tables and other stateful-structures that should not be
  dropped when you upgrade from one version to another. Each incremental script
  migrates your environment from one version of pgai to the next. You execute each
  incremental script exactly once. It is separate unit-of-work that either succeeds
  or fails.

  Incremental scripts are executed in alphanumeric order on file name. Once an incremental script is published
  in a release, you must not rename it. To facilitate migration, each incremental file is
  [wrapped](./sql/migration.sql). Each migration id is tracked in the `migration` table. For more information,
  see [./sql/head.sql](./sql/head.sql).

The installation workflow for the SQL scripts is:

1. **Clean your environment**: run `make clean-sql` to delete `./sql/ai--*<current-version>.sql`.

   The `<current-version>` is defined in `versions()` in [./build.py](./build.py).

1. **Build pgai**: run `make build-sql` to compile idempotent and incremental scripts
   into `./sql/ai--*<current-version>.sql`.
1. **Install pgai**: run `make install-sql` to install `./sql/ai--*.sql` and `./sql/ai*.control` into your local
   environment.

When you release a new version, add the `./sql/ai--*<current-version>.sql` scripts to this repo with your
pull request.


### Build the Python code in pgai

Python code used by the pgai is maintained in [<pgai_source_dir>/src](./src).

In order to support multiple versions of pgai in the same Postgres installation, each version of the Python code and
its associated dependencies is installed in `/usr/local/lib/pgai/<version>`

The installation workflow for the Python code is:

1. **Clean your environment**: run `make clean-py` to remove build artifacts from your developer environment.
1. **Install pgai**:
   To compile and install the python package with its associated dependencies.
   * Current version: run `make install-py`.
   * All previous versions: run `make install-prior-py`. 
1. **Uninstall pgai**: run `make uninstall-py` and delete all versions of the Python code from 
   `/usr/local/lib/pgai`.


### Versions prior to 0.4.0

Prior to pgai v0.4.0, Python dependencies were installed system-wide. Until pgai versions 0.1 - 0.3 are deprecated
[old dependencies](./src/old_requirements.txt) are installed system-wide.

