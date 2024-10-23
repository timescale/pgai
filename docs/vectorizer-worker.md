
# Run vectorizers in a self-hosted database using pgai vectorizer worker

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

## Prerequisites

To run vectorizer workers, you need to:

* Install:
  * Container environment: [Docker][docker]
  * Local environment: [Python3][python3] and [pip][pip]
  * All environments: A Postgres client like [psql][psql]
* Create a key for you AI provider:
  * [OpenAI][openai-key]

## Install and configure vectorizer worker

To be able to run vectorizers in your self-hosted database, either:

- [Install the timescaledb-ha Docker image](#install-the-timescaledb-ha-docker-image): a Docker image containing a complete local developer environment 
- [Install the vectorizer worker Docker image](#install-and-configure-vectorizer-worker): a Docker image you use to run vectorizers on any self-hosted Postgres database with the pgai 
   extension activated 
- [Install vectorizer worker in your local environment](#install-vectorizer-worker-in-your-local-environment-): install pgai locally so you can run vectorizers on any self-hosted
  Postgres database with the pgai extension activated

### Install the timescaledb-ha Docker image

This docker image supplies a Postgres deployment with the TimescaleDB and pgai extensions installed. You can develop and 
test pgai, vectorizers and vectorizer worker locally.

On your local machine:

1. **Create the Docker configuration for the timescaledb-ha image**

   Add the following docker configuration to `<timescale-folder>/docker-compose.yml`:
   ```
   name: pgai
   services:
     db:
       image: timescale/timescaledb-ha:cicd-024349a-arm64
       environment:
         POSTGRES_PASSWORD: postgres
         OPENAI_API_KEY: <your-api-key>
       ports:
         - "5432:5432"
       volumes:
         - ./data:/var/lib/postgresql/data
     vectorizer-worker:
       image: timescale/pgai-vectorizer-worker:0.1.0rc4
       environment:
         VECTORIZER_DB_URL: postgres://postgres:postgres@db:5432/postgres
         OPENAI_API_KEY: <your-api-key>
   ```

   1. Replace the instances of `<your-api-key>` with a key from you AI provider.
   
1. **Start the database**
   ```shell
    docker-compose up -d db
    ```

1. **Connect to your self-hosted database**
   - Docker: `docker exec -it pgai-db-1 psql -U postgres`
   - psql:  `psql postgres://postgres:postgres@localhost:5432/postgres`

  
### Install the vectorizer worker Docker image

This docker image supplies a pgai image with vectorizer worker. You use this image to 
run vectorizers on any self-hosted Postgres database that has the pgai extension activated.

On your local machine:

IAIN: Alejandro, I'm not too sure what to write here.
1. **Create the Docker configuration for the timescaledb-ha image**
1. **Setup the connection to your self-hosted database**

### Install vectorizer worker in your local environment 

On your local machine:

1. **Install [pgai](https://pypi.org/project/pgai/) from PyPI**

   ```bash
   pip install pgai
   ```

   The vectorizer worker, `pgai vectorizer worker` is now in your `$PATH`.

1. **Run the vectorizer worker**

    After you [define a vectorizer in your database](/docs/vectorizer.md#define-a-vectorizer), you run 
    a vectorizer worker to generate and run your embeddings:

    1. Set the connection string to your self-hosted database and the API key for the external embeddings
      provider as environment variables:

       ```bash
       export VECTORIZER_DB_URL="postgres://<user>:<password>@<host>:<port>/<dbname>"
       export OPENAI_API_KEY="Your OpenAI API key"
       ```

    1. Run the vectorizer worker:

       ```bash
       pgai vectorizer worker
       ```

    You can also use the `-d` or `--db-url` arguments to set a Postgres connection string:
    ```bash
    vectorizer -d "postgres://user:password@host:port/dbname"
    ```

## Run vectorizers with vectorizer worker

By default, when you run a vectorizer worker, it loops over the vectorizers defined in 
your database and processes each vectorizer in turn. Five minutes after completing each 
vectorizer run, the vectorizer worker loops over the vectorizers again. You can also use the 
`-i` / `--vectorizer-id` command line argument to manage which vectorizers that are run by that
worker instance. A vectorizer worker can:

- Run a single vectorizer:

  To run the vectorizer with id 42:
  ```bash
  pgai vectorizer worker -i 42
  ```

- Run multiple specific vectorizers: 

  To run the vectorizers with ids `42`, `64`, and `8`:

  ```bash
  pgai vectorizer worker -i 42 -i 64 -i 8
  ```

- Run multiple vectorizers in concurrent vectorizer workers:

  To run the vectorizers with id `42` and `64` in different vectorizer workers:
  1. In a first shell, run:

     ```bash
     pgai vectorizer worker -id 42
     ```

  1. In another shell, run: 

     ```bash
     pgai vectorizer worker -id 64
     ```

- Run concurrent vectorizer workers on a single vectorizer

  More than one vectorizer worker can efficiently process the same vectorizer id
  at the same time. To run the vectorizer with id `41` in different vectorizer workers:

  1. In a first shell, run:
  
     ```bash
     pgai vectorizer worker -id 42
     ```

  1. In another shell, run:

     ```bash
     pgai vectorizer worker -id 42
     ```

You find the vectorizers id in the `ai.vectorizer` table.

## Set the time between vectorizer worker runs

When you run a vectorizer worker, it loops over the vectorizers defined in your database.
Each vectorizer worker processes vectorizer queue until it is empty. By 
default, the vectorizer worker sleeps for five minutes, then start over.

To control the time between vectorizer worker iterations, set the integer seconds or a duration string 
in the `--poll-interval` parameter: 

- Run every hour:

  ```bash
  pgai vectorizer worker --poll-interval=1h
  ```

- Run every 45 minutes:

  ```bash
  pgai vectorizer worker --poll-interval=45m
  ```

- Run every 900 seconds:

  ```bash
  pgai vectorizer worker --poll-interval=900
  ```

- Run once and then exit: 

  ```bash
  pgai vectorizer worker --once
  ```
  This is useful if you want to run the vectorizer worker on a cron job.

### Set the number of asynchronous tasks running in a vectorizer worker

Use the `-c` / `--concurrency` option to cause the vectorizer worker to use 
multiple asynchronous tasks to process a queue:

```bash
pgai vectorizer worker -c 3
```


[python3]: https://www.python.org/downloads/
[pip]: https://pip.pypa.io/en/stable/installation/#supported-methods
[docker]: https://docs.docker.com/get-docker/
[psql]: https://www.timescale.com/blog/how-to-install-psql-on-mac-ubuntu-debian-windows/
[openai-key]: https://platform.openai.com/api-keys
