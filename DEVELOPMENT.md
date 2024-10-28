# Develop and test changes to pgai

pgai brings embedding and generation AI models closer to the database. Want to contribute to the pgai project?
Start here. 

This project is organized as a monorepo with two distributable bodies of code:

1. the pgai Postgres extension is located in [projects/extension](./projects/extension)
2. the [pgai python library/cli](https://pypi.org/project/pgai/) is located in [projects/pgai](./projects/pgai)

This page shows you:

- [How to work on the pgai extension](#working-on-the-pgai-extension)
- [How to work on the pgai library](#working-on-the-pgai-library)

## PRs and commits

The project uses [conventional commits][conventional-commits]. It's enforced by
CI, you won't be able to merge PRs if your commits do not comply. This helps us
automate the release process, changelog generation, etc.

If you don't want to wait for the CI to get feedback on you commit. You can
install the git hook that checks your commits locally. To do so, run:

```bash
cd projects/pgai
make install-commit-hook
```

## Working on the pgai extension

- [pgai extension development prerequisites](#pgai-extension-development-prerequisites)
- [The pgai extension development workflow](#the-pgai-extension-development-workflow)
- [Controlling pgai extension tests](#controlling-pgai-extension-tests)
- [The pgai extension architecture](#the-pgai-extension-architecture)

### pgai extension development prerequisites

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

### The pgai extension development workflow

To make changes to pgai:

1. Navigate to `projects/extension` in the directory where you cloned the repo.
2. Build the docker image
   ```bash
   make docker-build
   ```
3. Run the container:
   ```bash
   make docker-run
   ```
   The `projects/extension` directory is mounted to `/pgai` in the running container.

4. Work inside the container:
   * **Docker shell**:
      1. Open get a shell session in the container:

         ```bash
         make docker-shell
         ```
         You are logged in as root.

      2. Build and Install the extension

         ```bash
         make build
         make install
         ```

      3. Run the unit tests
         
         First run the test-server in a second shell
         ```bash
         make test-server
         ```
         Then, run the tests in the first shell
         ```bash
         make test
         ```

      5. Clean build artifacts

         ```bash
         make clean
         ```

      6. Uninstall the extension

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


### Controlling pgai extension tests

The [projects/extension/tests](./projects/extension/tests) directory contains the unit tests.

To set up the tests:

1. In a [.env](https://saurabh-kumar.com/python-dotenv/) file, use the following flags to enable/disable test suites
    ```text
    # enable/disable tests
    ENABLE_OPENAI_TESTS=1
    ENABLE_OLLAMA_TESTS=1
    ENABLE_ANTHROPIC_TESTS=1
    ENABLE_COHERE_TESTS=1
    ENABLE_VECTORIZER_TESTS=1
    ENABLE_DUMP_RESTORE_TESTS=1
    ENABLE_PRIVILEGES_TESTS=1
    ENABLE_CONTENTS_TESTS=1
    ENABLE_SECRETS_TESTS=1
    ```

2. Some tests require extra environment variables to be added to the .env file
   - **OpenAI**:
      - OPENAI_API_KEY - an [OpenAI API Key](https://platform.openai.com/api-keys) for OpenAI unit testing.
   - **Ollama**:
      - OLLAMA_HOST - the URL to the Ollama instance to use for testing. For example, `http://host.docker.internal:11434`.
   - **Anthropic**:
      - ANTHROPIC_API_KEY - an [Anthropic API Key](https://docs.anthropic.com/en/docs/quickstart#set-your-api-key) for Anthropic unit testing.
   - **Cohere**:
      - COHERE_API_KEY - a [Cohere API Key](https://docs.cohere.com/docs/rate-limits) for Cohere unit testing.


### The pgai extension architecture

pgai consists of [SQL](./projects/extension/sql) scripts and a [Python](./projects/extension/ai) package.

* [Develop SQL in pgai](#develop-sql-in-pgai)
* [Develop Python in pgai](#develop-python-in-pgai)
* [Versions prior to 0.4.0](#versions-prior-to-040):


#### Develop SQL in the pgai extension

SQL code used by pgai is maintained in [./projects/extension/sql](./projects/extension/sql).

The SQL is organized into:

* **Idempotent scripts**: maintained in [./projects/extension/sql/idempotent](./projects/extension/sql/idempotent).

  Idempotent scripts consist of `CREATE OR REPLACE` style statements, usually as
  functions. They are executed in alphanumeric order every time you install or
  upgrade pgai. In general, it is safe to rename these scripts from one version to
  the next.

* **Incremental scripts**: maintained in [./projects/extension/sql/incremental](./projects/extension/sql/incremental).

  Incremental files create tables and other stateful-structures that should not be
  dropped when you upgrade from one version to another. Each incremental script
  migrates your environment from one version of pgai to the next. You execute each
  incremental script exactly once. It is separate unit-of-work that either succeeds
  or fails.

  Incremental scripts are executed in alphanumeric order on file name. Once an incremental script is published
  in a release, you must not rename it. To facilitate migration, each incremental file is
  [wrapped](./projects/extension/sql/migration.sql). Each migration id is tracked in the `migration` table. For more information,
  see [./projects/extension/sql/head.sql](./projects/extension/sql/head.sql).

* **Built scripts**: `./projects/extension/sql/ai--*.sql`

  `make build` "compiles" the idempotent and incremental scripts into the final
  form that is installed into a postgres environment as an extension. A script
  named `./projects/extension/sql/ai--<current-version>.sql` is built. For every prior version
  (other than 0.1.0, 0.2.0, and 0.3.0), the file is copied to
  `./projects/extension/sql/ai--<prior-version>--<current-version>.sql` to give postgres an upgrade
  path from prior versions. The `./projects/extension/sql/ai.control` is also ensured to have the
  correct version listed in it.

  When you release a new version, add the `./projects/extension/sql/ai--*<current-version>.sql` scripts to this repo with your
  pull request. The scripts from prior versions are checked in and should not be modified after
  having been released.

If you are exclusively working on SQL, you may want to forego the high-level make
targets in favor of the SQL-specific make targets:

1. **Clean your environment**: run `make clean-sql` to delete `./projects/extension/sql/ai--*<current-version>.sql`.

   The `<current-version>` is defined in `versions()` in [./projects/extension/build.py](./projects/extension/build.py).

1. **Build pgai**: run `make build` to compile idempotent and incremental scripts
   into `./projects/extension/sql/ai--*<current-version>.sql`.
1. **Install pgai**: run `make install-sql` to install `./projects/extension/sql/ai--*.sql` and `./projects/extension/sql/ai*.control` into your local
   Postgres environment.

#### Develop Python in the pgai extension

Python code used by the pgai extension is maintained in [./projects/extension/ai](./projects/extension/ai).

Database functions
written in [plpython3u](https://www.postgresql.org/docs/current/plpython.html)
can import the modules in this package and any dependencies specified in
[./projects/extension/pyproject.toml](./projects/extension/pyproject.toml). 
Including the following line at the beginning of the database function body will 
allow you to import. The build process replaces this comment line with Python 
code that makes this possible. Note that the leading four spaces are required.

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


#### Versions prior to 0.4.0

Prior to pgai v0.4.0, Python dependencies were installed system-wide. Until pgai versions 0.1 - 0.3 are deprecated
[old dependencies](./src/old_requirements.txt) are installed system-wide.


## Working on the pgai library

The experience of working on the pgai library is like developing most Python
libraries and applications. Use the [requirements-dev.txt](./projects/pgai/requirements-dev.txt) 
file to create a virtual env for development.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Use the `help` target of the [Makefile](./projects/pgai/Makefile) to see what
commands are available.

```bash
make help
```

Be sure to add unit tests to the [tests](./projects/pgai/tests) directory when 
you add or modify code. Use the following commands to check your work before
submitting a PR.

```bash
make test
make lint
make format
make type-check
```

[conventional-commits]: https://www.conventionalcommits.org/en/v1.0.0/
