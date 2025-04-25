# Running on Timescale Cloud
When you install pgai on **Timescale Cloud**, the vectorizer worker is automatically activated and run on a schedule
so you don't need to do anything, everything just works out of the box.

**How it works**: When you deploy a pgai vectorizer on Timescale Cloud, the vectorizer worker is automatically activated and run on a schedule.
The scheduled job detects whether work is to be done for the vectorizers. If there is, the job runs the cloud function to embed the data.

**Disable the cloud function**: There are some instances in which you might want to run the vectorizer worker manually and disable the cloud function from running. You can do this by setting
[scheduling => ai.scheduling_none()](/docs/vectorizer/api-reference.md#scheduling-configuration) in the configuration for your vectorizer. Then you can run the 
vectorizer worker manually using the `pgai vectorizer worker` command or any other method discussed above.

> [!NOTE]
> Timescale Cloud currently does not support Ollama. To use Ollama on the data in your Timescale Cloud 
> service you need to disable the cloud function and run the vectorizer worker yourself.


# Running on self-hosted Postgres or other platforms

When you use pgai vectorizers on a self-hosted Postgres installation or another cloud provider other than Timescale Cloud, you have to run the vectorizer worker yourself. The vectorizer worker will connect to your database and process the vectorizers you have defined. You can run the vectorizer:
- Through the pgai CLI tool as `pgai vectorizer worker` (see [instructions below](#running-a-vectorizer-worker-as-a-cli-tool))
- Integrating the vectorizer worker as a background process into your own python application (see [instructions below](#running-a-vectorizer-worker-in-your-own-application))
- Using the vectorizer worker Docker image (see [instructions below](#running-a-vectorizer-worker-with-docker))
- In a Docker Compose configuration (see [instructions below](#running-a-vectorizer-worker-with-docker-compose))


## Running a vectorizer worker as a CLI tool

**Prerequisites**: [Python3][python3] and [pip][pip]


1. **Install [pgai](https://pypi.org/project/pgai/) from PyPI**

   ```shell
   pip install pgai
   ```

   The `pgai` command line tool should now be in your `$PATH`.
   
1. **Create a .env file**

   [Configure](#setting-api-keys-through-environment-variables-or-env-file) the API keys for your embedding providers by adding them to a `.env` file. For example, if you are using OpenAI, you can add the following:

   ```
   OPENAI_API_KEY=<your-openai-api-key>
   ```
   
   Alternatively, you can set the API key through an environment variable, but this is less secure.

1. **Run the vectorizer worker**

    After you [define a vectorizer in your database](/docs/vectorizer.md#define-a-vectorizer), you run 
    a vectorizer worker to generate and update your embeddings:
    
    ```shell
    pgai vectorizer worker -d <db-connection-string>
    ```

For more configuration options, see [Advanced configuration options](#advanced-configuration-options) below.

## Running a vectorizer worker in your own application 

 **Prerequisites**: [Python3][python3] and [pip][pip]

1. Add the pgai package dependency to your project

   ```shell
   pip install pgai
   ```
   or add `pgai` to the dependencies in your `requirements.txt` file, `pyproject.toml`, or similar configuration file.

2. Add the vectorizer worker to run in the background of your application

   ```python
   from pgai import Worker

   worker = Worker(db_url=<your-database-connection-string>)
   task = asyncio.create_task(worker.run())
   ```

   You can then shutdown the worker gracefully when your application shuts down:

   ```python
    
    await worker.request_graceful_shutdown()
    try:
        result = await asyncio.wait_for(task, timeout=20)
        if result is not None:
            print("Worker shutdown with exception:", result)
        else:
            print("Worker shutdown successfully")
    except asyncio.TimeoutError:
        print("Worker did not shutdown in time, it was killed")
   ```
   
3. Make sure you add the API keys for your embedding providers to the environment variables when you run 
  your application. 
  
    We recommend using a `.env` file to set the API key and then load the `.env` file using the `load_dotenv` function from the `python-dotenv` package.
    
    Alternatively, you can set the API key through an environment variable.
    
4. Run your application

For more configuration options, see [Advanced configuration options](#advanced-configuration-options) below.

## Running a vectorizer worker with Docker

**Prerequisites**:  [Docker][docker]

1. **Create a .env file**

    [Configure](#setting-api-keys-through-environment-variables-or-env-file) the API keys for your embedding providers by adding them to a `.env` file. For example, if you are using OpenAI, you can add the following:

   ```
   OPENAI_API_KEY=<your-openai-api-key>
   ```
   
   Alternatively, you can set the API key by passing it as an environment variable in the `docker run` command below, but this is less secure.

1. **Run the vectorizer worker**
  
    After you [define a vectorizer in your database](/docs/vectorizer.md#define-a-vectorizer), you run a vectorizer worker to generate and update your embeddings.

    ```
    docker run --env-file=.env timescale/pgai-vectorizer-worker:{tag version} --db-url <DB URL>
    ```

For more configuration options, see [Advanced configuration options](#advanced-configuration-options) below.

## Running a vectorizer worker with Docker Compose

Below is an end-to-end batteries-included Docker Compose configuration which you can use to test pgai vectorizers and and the vectorizer worker locally. It includes a:
- local Postgres instance,
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
        image: timescale/pgai-vectorizer-worker:latest
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

For more configuration options, see [Advanced configuration options](#advanced-configuration-options) below.

# Configure the vectorizer worker

Most users of the vectorizer worker will need to set the following configuration options:

- [Setting the database connection string](#setting-the-database-connection-string)
- [Setting API keys for embedding providers through environment variables (or .env file)](#setting-api-keys-through-environment-variables-or-env-file)

Other, advanced configuration options are available, see [Advanced configuration options](#advanced-configuration-options) below.

## Setting the database connection string

The vectorizer worker needs to know how to connect to your database. You can do this by setting the `-d` command line argument or the `PGAI_VECTORIZER_WORKER_DB_URL` environment variable.

For example, if you are using a local Postgres database, you can set the database connection string as follows:

```
pgai vectorizer worker -d postgres://postgres:postgres@localhost:5432/postgres
```


## Setting API keys through environment variables (or .env file)

If you are using an embedding provider that requires an API key (which most do),
you can set the API key through an environment variable or a .env file. We recommend
using a .env file to set the API key.

For example, if you are using OpenAI, you can set the API key in a .env file as follows:

```
OPENAI_API_KEY=<your-openai-api-key>
```

Or you can set the API key through an environment variable:

```
export OPENAI_API_KEY=<your-openai-api-key>
```


## Advanced configuration options

Most users of the vectorizer worker will be happy with the default configuration for all other options.
But, if you need to, you can control the following:

- The vectorizer ids that are processed by the vectorizer worker ([section below](#control-which-vectorizers-are-processed))
- The time between vectorizer worker runs ([section below](#set-the-time-between-vectorizer-worker-runs))
- The number of asynchronous tasks running in a vectorizer worker ([section below](#set-the-number-of-asynchronous-tasks-running-in-a-vectorizer-worker))
- Whether to run the vectorizer worker once and then exit ([section below](#run-the-vectorizer-worker-once-and-then-exit))

All of these options can be set through the command line arguments, environment variables, or through an argument to the `Worker` 
class constructor in the `pgai` Python package.

| Option | Command line argument | Environment variable | `Worker` class constructor argument |
|--------|-----------------------|--------------------|-------------------------------------|
| Control which vectorizers are processed | `-i` / `--vectorizer-id` | `PGAI_VECTORIZER_WORKER_VECTORIZER_IDS` | `vectorizer_ids` |
| Set the time between vectorizer worker runs | `--poll-interval` | `PGAI_VECTORIZER_WORKER_POLL_INTERVAL` | `poll_interval` |
| Set the number of asynchronous tasks running in a vectorizer worker | `-c` / `--concurrency` | `PGAI_VECTORIZER_WORKER_CONCURRENCY` | `concurrency` |
| Run the vectorizer worker once and then exit | `--once` | `PGAI_VECTORIZER_WORKER_ONCE` | `once` |


### Control which vectorizers are processed

If you want to run a vectorizer worker that only processes a subset of the vectorizers in your database,
you can do so by specifying the vectorizer ids you want to process. You can do this by using the 
`-i` / `--vectorizer-id` command line argument. 


A vectorizer worker can:

- Run all vectorizers:

  To run all current and future vectorizers:
  - cli: `pgai vectorizer worker`
  - python: `worker = Worker(db_url=<your-database-connection-string>)`
  - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version}`
  - Docker Compose: `command: []`

- Run a single vectorizer:

  To run the vectorizer with id 42:
  - cli: `pgai vectorizer worker -i 42`
  - python: `worker = Worker(db_url=<your-database-connection-string>, vectorizer_ids=[42])`
  - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} -i 42`
  - Docker Compose: `command: ["-i", "42"]`

- Run multiple specific vectorizers: 

  To run the vectorizers with ids `42`, `64`, and `8`:
  - cli: `pgai vectorizer worker -i 42 -i 64 -i 8`
  - python: `worker = Worker(db_url=<your-database-connection-string>, vectorizer_ids=[42, 64, 8])`
  - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} -i 42 -i 64 -i 8`
  - Docker Compose: `command: ["-i", "42", "-i", "64", "-i", "8"]`

- Run multiple vectorizers in concurrent vectorizer workers:

  To run the vectorizers with id `42` and `64` in different vectorizer workers:
  1. In a first shell, run:
     - cli: `pgai vectorizer worker -i 42`
     - python: `worker = Worker(db_url=<your-database-connection-string>, vectorizer_ids=[42])`
     - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version}  -i 42`
     - Docker Compose: `command: ["-i", "42"]`

  1. In another shell, run: 

     - cli: `pgai vectorizer worker -i 64`
     - python: `worker = Worker(db_url=<your-database-connection-string>, vectorizer_ids=[64])`
     - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} -i 64`
     - Docker Compose: `command: ["-i", "64"]`

- Run concurrent vectorizer workers on a single vectorizer

  More than one vectorizer worker can efficiently process the same vectorizer id
  at the same time. To run the vectorizer with id `41` in different vectorizer workers:

  1. In a first shell, run:

     - cli: `pgai vectorizer worker -i 42`
     - python: `worker = Worker(db_url=<your-database-connection-string>, vectorizer_ids=[42])`
     - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} -i 42`
     - Docker Compose: `command: ["-i", "42"]`

  1. In another shell, run:

     - cli: `pgai vectorizer worker -i 42`
     - python: `worker = Worker(db_url=<your-database-connection-string>, vectorizer_ids=[42])`
     - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} -i 42`
     - Docker Compose: `command: ["-i", "42"]`

You find the vectorizer ids in the `ai.vectorizer` table.

### Set the time between vectorizer worker runs

When you run a vectorizer worker, it loops over the vectorizers defined in your database.
Each vectorizer worker processes vectorizer queue until it is empty. By 
default, the vectorizer worker sleeps for five minutes, then start over.

To control the time between vectorizer worker iterations, set the integer seconds or a duration string 
in the `--poll-interval` parameter: 

- Run every hour:

  - cli: `pgai vectorizer worker --poll-interval=1h`
  - python: `worker = Worker(db_url=<your-database-connection-string>, poll_interval=timedelta(hours=1))`
  - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} --poll-interval=1h`
  - Docker Compose: `command: ["--poll-interval", "1h"]`

- Run every 45 minutes:

  - cli: `pgai vectorizer worker --poll-interval=45m`
  - python: `worker = Worker(db_url=<your-database-connection-string>, poll_interval=timedelta(minutes=45))`
  - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} --poll-interval=45m`
  - Docker Compose: `command: ["--poll-interval", "45m"]`

- Run every 900 seconds:

  - cli: `pgai vectorizer worker --poll-interval=900`
  - python: `worker = Worker(db_url=<your-database-connection-string>, poll_interval=timedelta(seconds=900))`
  - Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} --poll-interval=900`
  - Docker Compose: `command: ["--poll-interval", "900"]`
  
You can also make the vectorizer worker run only once by setting the `--once` flag. See [Run the vectorizer worker once and then exit](#run-the-vectorizer-worker-once-and-then-exit) for more details.

### Set the number of asynchronous tasks running in a vectorizer worker

Use the `-c` / `--concurrency` option to cause the vectorizer worker to use 
multiple asynchronous tasks to process a queue:

- cli: `pgai vectorizer worker -c 3`
- python: `worker = Worker(db_url=<your-database-connection-string>, concurrency=3)`
- Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} -c 3`
- Docker Compose: `command: ["-c", "3"]`

### Run the vectorizer worker once and then exit

You can run the vectorizer worker once and then exit by using the `--once` flag. This is useful for debugging or if you want to run the vectorizer worker in a cron job.

- cli: `pgai vectorizer worker --once`
- python: `worker = Worker(db_url=<your-database-connection-string>, once=True)`
- Docker: `docker run timescale/pgai-vectorizer-worker:{tag version} --once`
- Docker Compose: `command: ["--once"]`
                                  |


[python3]: https://www.python.org/downloads/
[pip]: https://pip.pypa.io/en/stable/installation/#supported-methods
[docker]: https://docs.docker.com/get-docker/
[psql]: https://www.timescale.com/blog/how-to-install-psql-on-mac-ubuntu-debian-windows/
[openai-key]: https://platform.openai.com/api-keys
[voyage-key]: https://docs.voyageai.com/docs/faq#how-do-i-get-the-voyage-api-key
