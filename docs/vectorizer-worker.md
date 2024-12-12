
# Run vectorizers using pgai vectorizer worker

When you install pgai on Timescale Cloud or another cloud installation, you use 
scheduling to control the times when vectorizers are run. A scheduled job detects whether work is to be done for the 
vectorizers. If there is, the job runs the cloud function to embed the data.

When you have [defined vectorizers](./vectorizer.md#define-a-vectorizer) on a self-hosted Postgres installation, you 
use vectorizer worker to asynchronously processes them. By default, when you run `pgai vectorizer worker`, it 
loops over the vectorizers defined in your database and processes each vectorizer in turn.

This page shows you how to install, run, and manage the workers that run vectorizers in your database:

- [Install and configure vectorizer worker](#install-and-configure-vectorizer-worker): setup the environment
  to securely run vectorizers defined in a self-hosted Postgres environment
- [Run vectorizers with vectorizer worker](#run-vectorizers-with-vectorizer-worker): run specific
  vectorizers in your database as either single, parallel or concurrent tasks
- [Set the time between vectorizer worker runs](#set-the-time-between-vectorizer-worker-runs): manage run scheduling
- [Additional configuration via environment variables](#additional-configuration-via-environment-variables) an overview of the environment variables and their purpose

## Prerequisites

To run vectorizer workers, you need to:

* Install:
  * Container environment: [Docker][docker]
  * Local environment: [Python3][python3] and [pip][pip]
  * All environments: A Postgres client like [psql][psql]
* Create a key for your AI provider:
  * [OpenAI][openai-key]
  * [Voyage AI][voyage-key]

## Install and configure vectorizer worker

To be able to run vectorizers in your self-hosted database, use one of the following setups:

- [End-to-end vectorizer worker with Docker Compose](#end-to-end-vectorizer-worker-with-docker-compose): a Docker Compose configuration with a database instance and pgai vectorizer worker
- [Standalone vectorizer worker with Docker](#standalone-vectorizer-worker-with-docker): a Docker image you use to run vectorizers on any self-hosted Postgres database with the pgai
   extension activated
- [Install vectorizer worker as a python package](#install-vectorizer-worker-as-a-python-package): install pgai as a python package so you can run vectorizers on any self-hosted
  Postgres database with the pgai extension activated

### End-to-end vectorizer worker with Docker Compose

The end-to-end vectorizer worker is a batteries-included Docker Compose
configuration which you use to test pgai, vectorizers and vectorizer worker
locally. It includes a:
- local Postgres instance with pgai installed,
- Ollama embedding API service
- pgai vectorizer worker

On your local machine:

1. **Copy the following configuration into a file named `compose.yaml`**

    ```yaml
    name: pgai
    services:
      db:
        image: timescale/timescaledb-ha:pg17
        environment:
          POSTGRES_PASSWORD: postgres
        ports:
          - "5432:5432"
        volumes:
          - data:/var/lib/postgresql/data
      vectorizer-worker:
        image: timescale/pgai-vectorizer-worker:v0.2.1
        environment:
          PGAI_VECTORIZER_WORKER_DB_URL: postgres://postgres:postgres@db:5432/postgres
          OLLAMA_HOST: http://ollama:11434
        command: [ "--poll-interval", "5s" ]
      ollama:
        image: ollama/ollama
    volumes:
      data:
    ```

1. **Start the services locally**
   ```shell
    docker compose up -d
    ```

1. **Connect to your self-hosted database**
   - Docker: `docker compose exec -it db psql`
   - psql:  `psql postgres://postgres:postgres@localhost:5432/postgres`

### Standalone vectorizer worker with Docker

The `timescale/pgai-vectorizer-worker` docker image supplies the pgai vectorizer worker.
You use this image to run vectorizers on any self-hosted Postgres database that has the
pgai extension activated.

On your local machine:

1. **Run the vectorizer worker**

   For self-hosted, you run a pgai vectorizer worker to automatically create embedding from the data in your
   database using [vectorizers you defined previously](/docs/vectorizer.md#define-a-vectorizer).

   Start the vectorizer worker:
   ```
   docker run timescale/pgai-vectorizer-worker:{tag version} --db-url <DB URL>
   ```

### Install vectorizer worker as a python package

On your local machine:

1. **Install [pgai](https://pypi.org/project/pgai/) from PyPI**

   ```shell
   pip install pgai
   ```

   The vectorizer worker, `pgai vectorizer worker` is now in your `$PATH`.

1. **Run the vectorizer worker**

    After you [define a vectorizer in your database](/docs/vectorizer.md#define-a-vectorizer), you run 
    a vectorizer worker to generate and update your embeddings:

    1. Configure environment variables if necessary (see [Additional configuration via environment variables](#additional-configuration-via-environment-variables))
       for a list of the available environment variables:

       ```bash
       export OPENAI_API_KEY="..."
       ```

    1. Run the vectorizer worker:

       ```shell
       pgai vectorizer worker -d <db-connection-string>
       ```

## Run vectorizers with vectorizer worker

By default, when you run a vectorizer worker, it loops over the vectorizers defined in 
your database and processes each vectorizer in turn. Five minutes after completing each 
vectorizer run, the vectorizer worker loops over the vectorizers again. 
For a [local installation](#install-vectorizer-worker-in-your-local-environment-), you use the 
`-i` / `--vectorizer-id` command line argument to manage which vectorizers that are run by that
worker instance. For `docker compose` you add arguments using either the `command` or `environment`
flags in `compose.yaml`.

A vectorizer worker can:

- Run all vectorizers:

  To run all current and future vectorizers:
  - local: `pgai vectorizer worker`
  - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version}`
  - Docker Compose: `command: []`

- Run a single vectorizer:

  To run the vectorizer with id 42:
  - local: `pgai vectorizer worker -i 42`
  - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} -i 42`
  - Docker Compose: `command: ["-i", "42"]`

- Run multiple specific vectorizers: 

  To run the vectorizers with ids `42`, `64`, and `8`:
  - local: `pgai vectorizer worker -i 42 -i 64 -i 8`
  - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} -i 42 -i 64 -i 8`
  - Docker Compose: `command: ["-i", "42", "-i", "64", "-i", "8"]`

- Run multiple vectorizers in concurrent vectorizer workers:

  To run the vectorizers with id `42` and `64` in different vectorizer workers:
  1. In a first shell, run:
     - local: `pgai vectorizer worker -i 42`
     - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version}  -i 42`
     - Docker Compose: `command: ["-i", "42"]`

  1. In another shell, run: 

     - local: `pgai vectorizer worker -i 64`
     - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} -i 64`
     - Docker Compose: `command: ["-i", "64"]`

- Run concurrent vectorizer workers on a single vectorizer

  More than one vectorizer worker can efficiently process the same vectorizer id
  at the same time. To run the vectorizer with id `41` in different vectorizer workers:

  1. In a first shell, run:

     - local: `pgai vectorizer worker -i 42`
     - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} -i 42`
     - Docker Compose: `command: ["-i", "42"]`

  1. In another shell, run:

     - local: `pgai vectorizer worker -i 42`
     - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} -i 42`
     - Docker Compose: `command: ["-i", "42"]`

You find the vectorizer ids in the `ai.vectorizer` table.

## Set the time between vectorizer worker runs

When you run a vectorizer worker, it loops over the vectorizers defined in your database.
Each vectorizer worker processes vectorizer queue until it is empty. By 
default, the vectorizer worker sleeps for five minutes, then start over.

To control the time between vectorizer worker iterations, set the integer seconds or a duration string 
in the `--poll-interval` parameter: 

- Run every hour:

  - local: `pgai vectorizer worker --poll-interval=1h`
  - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} --poll-interval=1h`
  - Docker Compose: `command: ["--poll-interval", "1h"]`

- Run every 45 minutes:

  - local: `pgai vectorizer worker --poll-interval=45m`
  - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} --poll-interval=45m`
  - Docker Compose: `command: ["--poll-interval", "45m"]`

- Run every 900 seconds:

  - local: `pgai vectorizer worker --poll-interval=900`
  - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} --poll-interval=900`
  - Docker Compose: `command: ["--poll-interval", "900"]`

- Run once and then exit: 

  - local: `pgai vectorizer worker --once`
  - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} --once`
  - Docker Compose: `command: ["--once"]`

  This is useful if you want to run the vectorizer worker on a cron job.

### Set the number of asynchronous tasks running in a vectorizer worker

Use the `-c` / `--concurrency` option to cause the vectorizer worker to use 
multiple asynchronous tasks to process a queue:

- local: `pgai vectorizer worker -c 3`
- Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} -c 3`
- Docker Compose: `command: ["-c", "3"]`

## Additional configuration via environment variables

Some important internals of the vectorizer worker are configured through
the following environment variables.

| Environment Variable                        | Default                | Purpose                                                                                   |
|---------------------------------------------|------------------------|-------------------------------------------------------------------------------------------|
| PGAI_VECTORIZER_WORKER_DB_URL               | -                      | Configures the database url that the vectorizer worker uses to procesa vectorizers.       |
| OPENAI_API_KEY                              | -                      | The API key that the vectorizer worker uses to authenticate against the OpenAI API.       |
| VOYAGE_API_KEY                              | -                      | The API key that the vectorizer worker uses to authenticate against the Voyage AI API.    |
| OLLAMA_HOST                                 | http://localhost:11434 | The host to use when communicating with the Ollama API.                                   |
| PGAI_VECTORIZER_OLLAMA_MAX_CHUNKS_PER_BATCH | 2048                   | Configures the number of chunks of data embedded in one Ollama API call, defaults to 2048 |


[python3]: https://www.python.org/downloads/
[pip]: https://pip.pypa.io/en/stable/installation/#supported-methods
[docker]: https://docs.docker.com/get-docker/
[psql]: https://www.timescale.com/blog/how-to-install-psql-on-mac-ubuntu-debian-windows/
[openai-key]: https://platform.openai.com/api-keys
[voyage-key]: https://dash.voyageai.com/api-keys
