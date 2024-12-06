# Develop and test changes to pgai

pgai brings embedding and generation AI models closer to the database. Want to contribute to the pgai project?
Start here.

[Just](https://github.com/casey/just) is used to run project commands. We are
not using any of the Make capabilities for compiling, and Just provides a nice
interface to interact with monorepos. Just is available in most [package
managers] (https://github.com/casey/just?tab=readme-ov-file#packages).

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
just install-commit-hook
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

1. Build the docker image
   ```bash
   just ext docker-build
   ```
1. Run the container:
   ```bash
   just ext docker-run
   ```
   The `projects/extension` directory is mounted to `/pgai` in the running container.

1. Work inside the container:
   * **Docker shell**:
      1. Open get a shell session in the container:

         ```bash
         just ext docker-shell
         ```
         You are logged in as root.

      1. Build and Install the extension

         ```bash
         just ext build
         just ext install
         ```

      1. Run the unit tests

         First run the test-server in a second shell
         ```bash
         just ext test-server
         ```
         Then, run the tests in the first shell
         ```bash
         just ext test
         ```

      1. Clean build artifacts

         ```bash
         just ext clean
         ```

      1. Uninstall the extension

         ```bash
         just ext uninstall
         ```

   * **psql shell**:
      1. To get a psql shell to the database in the docker container:

         ```bash
         just ext psql-shell
         ```

1. Stop and delete the container:

   ```bash
   # Stop the container
   just ext docker-stop
   # Delete the container
   just ext docker-rm
   ```


### Controlling pgai extension tests

The [projects/extension/tests](./projects/extension/tests) directory contains the unit tests.

To set up the tests:

1. In a [.env](https://saurabh-kumar.com/python-dotenv/) file, use the following flags to enable/disable test suites
    ```text
    # enable/disable tests
    ENABLE_VECTORIZER_TESTS=1
    ENABLE_DUMP_RESTORE_TESTS=1
    ENABLE_PRIVILEGES_TESTS=1
    ENABLE_CONTENTS_TESTS=1
    ENABLE_SECRETS_TESTS=1
    ```

2. Some tests require extra environment variables to be added to the .env file
   - **OpenAI**:
      - `OPENAI_API_KEY` - an [OpenAI API Key](https://platform.openai.com/api-keys) for OpenAI unit testing.
   - **Ollama**:
      - `OLLAMA_HOST` - the URL to the Ollama instance to use for testing. For example, `http://host.docker.internal:11434`.
   - **Anthropic**:
      - `ANTHROPIC_API_KEY` - an [Anthropic API Key](https://docs.anthropic.com/en/docs/quickstart#set-your-api-key) for Anthropic unit testing.
   - **Cohere**:
      - `COHERE_API_KEY` - a [Cohere API Key](https://docs.cohere.com/docs/rate-limits) for Cohere unit testing.
   - **Voyage**:
      - `VOYAGE_API_KEY` - a [Voyage API Key](https://voyageai.com) for Voyage unit testing.

   Providing these keys automatically enables the corresponding tests.


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

  `just ext build` "compiles" the idempotent and incremental scripts into the final
  form that is installed into a postgres environment as an extension. A script
  named `./projects/extension/sql/ai--<current-version>.sql` is built. For every prior version
  (other than 0.1.0, 0.2.0, and 0.3.0), the file is copied to
  `./projects/extension/sql/ai--<prior-version>--<current-version>.sql` to give postgres an upgrade
  path from prior versions. The `./projects/extension/sql/ai.control` is also ensured to have the
  correct version listed in it.

  When you release a new version, add the `./projects/extension/sql/ai--*<current-version>.sql` scripts to this repo with your
  pull request. The scripts from prior versions are checked in and should not be modified after
  having been released.

If you are exclusively working on SQL, you may want to forego the high-level just
recipes in favor of the SQL-specific just recipes:

1. **Clean your environment**: run `just ext clean-sql` to delete `./projects/extension/sql/ai--*<current-version>.sql`.

   The `<current-version>` is defined in `versions()` in [./projects/extension/build.py](./projects/extension/build.py).

1. **Build pgai**: run `just ext build` to compile idempotent and incremental scripts
   into `./projects/extension/sql/ai--*<current-version>.sql`.
1. **Install pgai**: run `just ext install-sql` to install `./projects/extension/sql/ai--*.sql` and `./projects/extension/sql/ai*.control` into your local
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

If you are exclusively working on Python, you may want to forego the high-level just
recipes in favor of the Python-specific ones:

1. **Clean your environment**: run `just ext clean-py` to remove build artifacts from your developer environment.
1. **Install pgai**:
   To compile and install the python package with its associated dependencies.
   * Current version: run `just ext install-py`.
   * Versions prior to 0.4.0: run `just ext install-prior-py`.
1. **Uninstall pgai**: run `just ext uninstall-py` and delete all versions of the Python code from
   `/usr/local/lib/pgai`.


#### Building prerelease versions of the extension

We would like to avoid long-lived feature branches and the git headaches that entails. 
Yet some features take a while to mature to a level that we are happy to ship and 
support in production environments. Avoiding feature branches means we may be in 
a position where we need to ship but have SQL code that is not fully ready. 
Making changes to SQL objects once they ship is tricky and painful and should be 
minimized.

We want to:
- avoid long-lived feature branches. 
- merge progress to main
- minimize database migrations that alter existing objects
- avoid installing prerelease code in production databases
- allow prerelease code to be installed/tested/trialed in an opt-in manner
- warn when prerelease code is installed
- avoid supporting extension upgrades after prerelease code has been installed

To this end, we allow prerelease functionality to be gated behind feature flags.
We only build and ship prerelease code if the version being built includes a 
prerelease tag. If the version is a production version, we omit the prerelease 
code altogether. Furthermore, if the feature flag is not enabled, the prerelease 
code is NOT executed/installed. 

Incremental or idempotent files numbered greater than 899 and lower than 999 must have a comment at 
the top of the file with a prefix of `--FEATURE-FLAG: ` followed by the name of 
a feature flag. These files are not executed AT ALL unless a session-level GUC 
like `ai.enable_feature_flag_<feature-flag>` is set to `true` when the 
`create extension` or `alter extension ... update` statement is executed.

Incremental/idempotent files numbered less than 900 must NOT have a feature flag 
comment.

Zero or more feature flag GUCs may be enabled at once. Flags that are enabled
when creating/updating the extension are recorded in the `ai.feature_flag` table.

Since feature-flag-gated code is only built and shipped for prerelease versions
in the first place, it can only be installed in an environment not intended for
production in the first place. If one or more feature flag GUCs is enabled, 
all bets are off. The code is pre-production, may not work, is not supported, 
**and upgrades from this state are not supported**. This is a dead-end state.

We do not generate upgrade paths from prerelease versions to production versions.

When working on pre-release features, tests can be written for these features. 
The tests must create a database, enable the correct feature flag, create the 
extension, and then proceed with testing.

**Example:**

```sql
select set_config('ai.enable_feature_flag_my_new_feature', 'true', false);

create extension ai cascade;
NOTICE:  installing required extension "vector"
NOTICE:  installing required extension "plpython3u"
WARNING:  Feature flag "ai.enable_feature_flag_my_new_feature" has been enabled. Pre-release software will be installed. This code is not production-grade, is not guaranteed to work, and is not supported in any way. Extension upgrades are not supported once pre-release software has been installed.
CREATE EXTENSION
```

Once a feature that was gated is finally blessed and "finished", we need a final 
PR that moves the incremental and idempotent SQL files to their final 
(less than 900) places and removes the feature flag comment. Changes to existing 
code/structures that were previously in a gated file could be folded into the 
original file. Tests must be updated to remove the feature flag references.

Frequently, working on new features requires changes to existing SQL code/structures. 
In the case of gated features, we are not able to make changes inline where the 
original code is defined. These changes have to be included in the gated files. 
While this may be somewhat awkward, it works, and it clearly delineates what 
changes to existing stuff are required for a new feature.

#### Versions prior to 0.4.0

Prior to pgai v0.4.0, Python dependencies were installed system-wide. Until pgai versions 0.1 - 0.3 are deprecated
[old dependencies](./src/old_requirements.txt) are installed system-wide.


## Working on the pgai library

The experience of working on the pgai library is like developing most Python
libraries and applications. We use [uv](https://docs.astral.sh/uv/getting-started/installation/) to manage dependencies and python versions. Once you have uv installed it's easy to get started.

Note: We try to somewhat follow the python release schedule for supported versions to allow more users to use our library.
Therefore we are about a year behind the latest python release.

Uv syncs the dependencies of all developers working on the project via the uv.lock file. If you want to add a new dependency make use of the uv add command:

```bash
uv add --directory projects/pgai <package-name>
```

If it is a development dependency and not needed at runtime, you can add the --dev flag:

```bash
uv add --directory projects/pgai --dev <package-name>
```

Uv installs all dependencies inside a virtual environment by default you can either activate this via the `uv shell` command or run commands directly via `uv run`.

For the most common commands use the just recipes.

```bash
just -l pgai
```

Be sure to add unit tests to the [tests](./projects/pgai/tests) directory when
you add or modify code. Use the following commands to check your work before
submitting a PR.

```bash
just pgai test
just pgai lint
just pgai format
just pgai type-check
```

[conventional-commits]: https://www.conventionalcommits.org/en/v1.0.0/
