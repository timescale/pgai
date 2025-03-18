## Working on the pgai library

Note: We try to somewhat follow the python release schedule for supported versions to allow more users to use our library.
Therefore, we are about a year behind the latest python release.

### Set up your environment

The experience of working on the pgai library is like developing most Python
libraries and applications. We use [uv](https://docs.astral.sh/uv/getting-started/installation/) to manage dependencies and python versions. Once you have uv installed it's easy to get started.

Make sure your uv version is at least `0.5.x`.

```bash
uv --version
```

If not, upgrade it with this command.

```bash
uv self update
```

Change directory into the [projects/pgai](/projects/pgai) directory and create a
virtual environment. Then, activate it.

```bash
cd projects/pgai
uv venv
source .venv/bin/activate
```

Install the project's dependencies into the virtual environment.

```bash
uv sync --all-extras
```

The vectorizer worker and some tests use environment variables and can make use
of a `.env` file. Creating one may make your life easier. Include the variables
below as you see fit.

```text
OLLAMA_HOST=""
OPENAI_API_KEY=""
VOYAGE_API_KEY=""
MISTRAL_API_KEY=""
COHERE_API_KEY=""
HUGGINGFACE_API_KEY=""
AZURE_OPENAI_API_KEY=""
AZURE_OPENAI_API_BASE=""
AZURE_OPENAI_API_VERSION=""
ENABLE_VECTORIZER_TOOL_TESTS=1
```

Run the tests to verify you have a working environment.

```bash
just test
```

### Manage Python Dependencies

Uv syncs the dependencies of all developers working on the project via the uv.lock file. If you want to add a new dependency make use of the uv add command:

```bash
uv add --directory projects/pgai <package-name>
```

If it is a development dependency and not needed at runtime, you can add the --dev flag:

```bash
uv add --directory projects/pgai --dev <package-name>
```

### Working with the project

We use [just](https://just.systems/man/en/) to define and run commands to work
with the project. These include tasks like building, installation, linting,
and running tests. To see a list of the available commands, run the following
from the root of the repo:

```bash
just -l pgai
```

### Testing the pgai library

Be sure to add unit tests to the [tests](/projects/pgai/tests) directory when
you add or modify code. Use the following commands to check your work before
submitting a PR.

```bash
just pgai test
just pgai lint
just pgai format
just pgai type-check
```

## Docker development environment

The following lines provide instructions for setting up and running the `pgai` development environment using Docker Compose. The setup consists of two primary services:

- **db**: A PostgreSQL database instance with persistent storage. Built from source using the [extension's Dockerfile](../extension/Dockerfile).
- **pgai-installer**: An ephemeral service that installs `pgai` in the database.
- **vectorizer-worker**: The vectorizer worker service that connects to the PostgreSQL database and performs vectorization tasks. Built from source using the [Dockerfile](./Dockerfile).

Files involved in the setup:

```
├── compose-dev.yaml              # The actual Docker Compose file
├── .env                          # Optional environment variables that applies to all services
├── db.env                        # Database-specific environment variables
├── worker.env                    # Vectorizer-worker-specific environment variables
├── Dockerfile                    # Dockerfile for the vectorizer worker service
└── ../extension/Dockerfile       # Dockerfile for the PostgreSQL database with the pgai extension preloaded
```

### Running the services

To start the services, run:

```sh
docker compose -f compose-dev.yaml up -d
```

### Stopping the Services

To stop the services, run:

```sh
docker compose -f compose-dev.yaml down
```

This will stop and remove the running containers but retain the named volume (`data`).

### Accessing the Database

You can connect to the database using `psql`:

```shell
docker compose -f compose-dev.yaml exec -it db psql -U postgres
```

Alternatively, you can connect using any other client by specifying the following connection uri: `postgresql://postgres:postgres@localhost`. e.g.:

```sh
psql 'postgresql://postgres:postgres@localhost'
```

### Viewing logs

To see logs for all services:

```sh
docker compose -f compose-dev.yaml logs -f
```

To see logs for a specific service (e.g., `vectorizer-worker`):

```sh
docker compose -f compose-dev.yaml logs -f vectorizer-worker
```

### Environment variables

You can define additional environment variables in the following `*.env` files:

- `.env`: environment variables that applies to all services.
- `db.env`: environment variables that apply to the `db` service.
- `worker.env`: environment variables that apply to the `vectorizer-worker` service.

### Cleaning up

To remove all containers, networks, and volumes, run:

```sh
docker compose -f compose-dev.yaml down -v
```

Alternatively, if the containers are already stopped, you can run:

```sh
docker compose -f compose-dev.yaml rm -v
```

Both options will **delete** the persistent database volume (`data`).

## Making sure concurrency is working correctly

Making sure concurrency is working correctly is a bit tricky and manual for now. An easy way to see if concurrency is working is to run the following command:

```bash
uv run pytest -k test_process_vectorizer\[4 -rP
```

This will run the openai test with concurrency and print the output to the console. Then you have to verify the logs look interleaved between the two workers.

## Running Benchmarks

This guide explains how to run and customize benchmarks for the pgai vectorizer
using the provided just recipes.

## Setup

The benchmarks use a Docker container with PostgreSQL and a sample Wikipedia
dataset. The benchmark recipes handle:

1. Building and starting the container.
1. Loading sample data.
1. Creating a vectorizer.
1. Running memory or CPU profiling.

## Customizing Benchmarks

You can customize the benchmarks using the following variables when running the
just commands:

### Dataset Size Control

```bash
# Limit the number of wiki articles to process (default: "off")
just total_items=100 benchmark-mem

# Increase content size by repeating article body (default: "off")
just repeat_content=3 benchmark-mem
```

- `total_items`: When set, keeps only the specified number of articles in the
  wiki table. Use this to run quick benchmarks with a smaller dataset.

  - Example: `total_items=100` will keep only 100 articles.
  - When "off", uses the full dataset.

- `repeat_content`: Multiplies the content size of each article by the
  specified number. Use this to test how the vectorizer handles larger chunks
  of text.
  - Example: `repeat_content=3` will triple the size of each article's body
  - When "off", uses original content size

### VCR Settings

The CPU benchmarks use VCR.py to record and replay OpenAI API calls, making the
benchmarks reproducible and avoiding API costs during testing. We don't use
them for memory benchmarks since handling the cassette has memory implications.

```bash
# Use a specific cassette file (default: "wiki_openai_500")
just vcr_cassette=my_test_case benchmark-cpu

# Change recording mode (default: "once")
just vcr_record_mode=new_episodes benchmark-cpu
```

- `vcr_cassette`: Specifies which cassette file to use for recording/replaying
  API calls.

  - Files are stored in `benchmark/cassettes/`
  - Default is "wiki_openai_500" which contains responses for 500 wiki
    articles.

- `vcr_record_mode`: Controls how VCR.py handles API calls.
  - `once`: Record the call once, then always replay.
  - `new_episodes`: Use existing recordings but record any new calls.
  - `none`: Only use existing recordings, fail on new calls.
  - `all`: Always record new responses, overwriting existing ones.

## Example Usage

- Run a memory benchmark with a small dataset:

```bash
just total_items=50 benchmark-mem
```

- Run a CPU benchmark with larger chunks:

```bash
just repeat_content=2 benchmark-cpu
```

- Record new API responses for a custom test:

```bash
just vcr_cassette=my_custom_test vcr_record_mode=new_episodes benchmark-cpu
```

- Quick benchmark with both size controls:

```bash
just total_items=10 repeat_content=2 benchmark-mem
```

- Run benchmark and keep container for manual tests:

```bash
just keep_container=true benchmark-mem
```

## Available Benchmark Commands

- `benchmark-mem`: Runs memory profiling using memray.
- `benchmark-cpu`: Runs CPU profiling using py-spy, generating a flamegraph.
- `benchmark-cpu-top`: Shows real-time CPU usage in a top-like interface.
- `benchmark-queue-count`: Monitors the number of items in the vectorizer
  queue.

## Notes

- Memory benchmarks don't use VCR by default and will make real API calls
- CPU benchmarks always use VCR to ensure consistent results.
- The benchmark container is automatically cleaned up before each run. If you
  want to keep the container for manual checks, run the command with
  `keep__container=true`.
- Results are stored in `benchmark/results/` with timestamps.
