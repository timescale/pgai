# Develop and test changes to pgai

pgai brings embedding and generation AI models closer to the database. Want to contribute to the pgai project?
Start here. This page shows you:

- [The pgai development workflow](#the-pgai-development-workflow): build, run and test pgai in a Docker container.
- [How to test pgai](#test-pgai): use the psql script to test your changes to pgai.
- [The pgai build architecture](#the-pgai-build-architecture): work with multiple versions of pgai in the same environment.

## PRs and commits

The project uses [conventional commits][conventional-commits]. It's enforce by
CI, you won't be able to merge PRs if your commits do not comply. This helps us
automate the release process, changelog generation, etc.

If you don't want to wait for the CI to get feedback on you commit. You can
install the git hook that checks your commits locally. To do so, run:

```bash
make install-git-hooks
```

## pgai Prerequisites

To make changes to the pgai extension, do the following in your developer environment:

* Install:
   * [Python3](https://www.python.org/downloads/).
   * [Docker](https://docs.docker.com/get-docker/).
   * A Postgres client like [psql](https://www.timescale.com/blog/how-to-install-psql-on-mac-ubuntu-debian-windows/) or [PopSQL](https://docs.timescale.com/use-timescale/latest/popsql/).
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

1. Navigate to directory where you cloned the repo.
2. Build the docker image
   ```bash
   make docker-build
   ```
3. Run the container:
   ```bash
   make docker-run
   ```
   The repo directory is mounted to `/pgai` in the running container.

4. Work inside the container:
   * **Docker shell**:
      1. Open get a shell session in the container:

         ```bash
         make docker-shell
         ```
         You are logged in as root.

      2. Install the extension

         ```bash
         make install
         ```

      3. Run the unit tests

         ```bash
         make test
         ```

      4. Clean build artifacts

         ```bash
         make clean
         ```

      5. Uninstall the extension

         ```bash
         make uninstall
         ```

   * **psql shell**:
      1. To get a psql shell to the database in the docker container:

         ```shell
         make psql-shell
         ```

7. Stop and delete the container:

   ```shell
   # Stop the container
   make docker-stop
   # Delete the container
   make docker-rm
   ```


## Test pgai

The [tests](./tests) directory contains the unit tests.

To set up the pgai tests:

1. In a [.env](https://saurabh-kumar.com/python-dotenv/) file, add the variables associated with the component(s) you want to test:
   - **OpenAI**:
      - ENABLE_OPENAI_TESTS - set to `1` to enable OpenAI unit tests.
      - OPENAI_API_KEY - an [OpenAI API Key](https://platform.openai.com/api-keys) for OpenAI unit testing.
   - **Ollama**:
      - ENABLE_OLLAMA_TESTS - set to `1` to enable Ollama unit tests.
      - OLLAMA_HOST - the URL to the Ollama instance to use for testing. For example, `http://host.docker.internal:11434`.
   - **Anthropic**:
      - ENABLE_ANTHROPIC_TESTS - set to `1` to enable Anthropic unit tests.
      - ANTHROPIC_API_KEY - an [Anthropic API Key](https://docs.anthropic.com/en/docs/quickstart#set-your-api-key) for Anthropic unit testing.
   - **Cohere**:
      - ENABLE_COHERE_TESTS - set to `1` to enable Cohere unit tests.
      - COHERE_API_KEY - a [Cohere API Key](https://docs.cohere.com/docs/rate-limits) for Cohere unit testing.

2. If you have made changes to the source, from a Docker shell, install the extension:
   ```bash
   make docker-shell
   make install
   ```
   You are in a Docker shell.

3. Run the tests

   ```bash
   make test
   ```

   This runs pytest against the unit tests in the [./tests](./tests) directory:
   1. Drops the `test` database.
   2. Creates the `test` database.
   3. Creates the `test` database user.
   4. Runs the tests against the `test` database.
   5. The `test` database and `test` user are left after the tests run for debugging

Best practice is to add new tests when you commit new functionality.

## The pgai architecture

pgai consists of [SQL](./sql) scripts and a [Python](./src) package.

* [Develop SQL in pgai](#develop-sql-in-pgai)
* [Develop Python in pgai](#develop-python-in-pgai)
* [Versions prior to 0.4.0](#versions-prior-to-040):


### Develop SQL in pgai

SQL code used by pgai is maintained in [./sql](./sql).

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

* **Built scripts**: `./sql/ai--*.sql`

  `make build-sql` "compiles" the idempotent and incremental scripts into the final
  form that is installed into a postgres environment as an extension. A script
  named `./sql/ai--<current-version>.sql` is built. For every prior version
  (other than 0.1.0, 0.2.0, and 0.3.0), the file is copied to
  `./sql/ai--<prior-version>--<current-version>.sql` to give postgres an upgrade
  path from prior versions. The `./sql/ai.control` is also ensured to have the
  correct version listed in it.

  When you release a new version, add the `./sql/ai--*<current-version>.sql` scripts to this repo with your
  pull request. The scripts from prior versions are checked in and should not be modified after
  having been released.

If you are exclusively working on SQL, you may want to forego the high-level make
targets in favor of the SQL-specific make targets:

1. **Clean your environment**: run `make clean-sql` to delete `./sql/ai--*<current-version>.sql`.

   The `<current-version>` is defined in `versions()` in [./build.py](./build.py).

1. **Build pgai**: run `make build-sql` to compile idempotent and incremental scripts
   into `./sql/ai--*<current-version>.sql`.
1. **Install pgai**: run `make install-sql` to install `./sql/ai--*.sql` and `./sql/ai*.control` into your local
   environment.


### Develop Python in pgai

Python code used by the pgai is maintained in [./src](./src).

Database functions
written in [plpython3u](https://www.postgresql.org/docs/current/plpython.html)
can import the modules in this package and any dependencies specified in
[./src/pyproject.toml](./src/pyproject.toml). Including the following line at the
beginning of the database function body will allow you to import. The
build process replaces this comment line with Python code that makes this
possible. Note that the leading four spaces are required.

```python
    #ADD-PYTHON-LIB-DIR
```

In order to support multiple versions of pgai in the same Postgres installation, each version of the Python code and
its associated dependencies is installed in `/usr/local/lib/pgai/<version>`

If you are exclusively working on Python, you may want to forego the high-level make
targets in favor of the Python-specific make targets:

1. **Clean your environment**: run `make clean-py` to remove build artifacts from your developer environment.
1. **Install pgai**:
   To compile and install the python package with its associated dependencies.
   * Current version: run `make install-py`.
   * Versions prior to 0.4.0: run `make install-prior-py`.
1. **Uninstall pgai**: run `make uninstall-py` and delete all versions of the Python code from
   `/usr/local/lib/pgai`.


### Versions prior to 0.4.0

Prior to pgai v0.4.0, Python dependencies were installed system-wide. Until pgai versions 0.1 - 0.3 are deprecated
[old dependencies](./src/old_requirements.txt) are installed system-wide.

[conventional-commits]: https://www.conventionalcommits.org/en/v1.0.0/
