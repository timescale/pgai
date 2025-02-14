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

- **db**: A PostgreSQL database instance with persistent storage and the `pgai` extension preloaded. Built from source using the [extension's Dockerfile](../extension/Dockerfile).
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

> [!IMPORTANT]  
> Even though the pgai extension is loaded, it is not installed by default. Read below.

#### Installing the pgai extension
To install the `pgai` extension, connect to the database and run:

```sql
CREATE EXTENSION IF NOT EXISTS ai cascade;
```

Alternatively, you can run the following command from the host machine:

```sh
docker compose --file compose-dev.yaml exec -t db psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS ai cascade;"
```
`
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
