# Run vectorizers in a self-hosted database using Vectorizer CLI

When you install pgai on Timescale Cloud or another cloud installation, you use 
scheduling to control the times when vectorizers are run. A scheduled job detects whether work is to be done for the vectorizers. If there is, the job runs the cloud function to 
embed the data.

When you have [defined vectorizers](./vectorizer.md#define-a-vectorizer) on a self-hosted Postgres installation, you 
run workers in Vectorizer CLI to asynchronously processes them. By default, when you run the `vectorizer` worker, it 
loops over the vectorizers defined in your database and processes each vectorizer in turn.

This page shows you how to install and run and manage the workers that run the vectorizers in your database:

- [Install and configure Vectorizer CLI](#install-and-configure-vectorizer-cli): setup the environment
  to securely run vectorizers defined in a self-hosted Postgres installation
- [Run vectorizers workers from Vectorizer CLI](#run-vectorizers-workers-from-vectorizer-cli): run specific
  vectorizers in your database as either single, parallel or concurrent tasks
- [Set the time between vectorizer worker runs](#set-the-time-between-vectorizer-worker-runs): control the time between 
  vectorizer worker runs

## Prerequisites

To use vectorizer worker you need:
- [Python3][python3] and [pip][pip] installed system-wide on the machine you run vectorizer workers
- A self-hosted Postgres database with [pgai installed](/README.md#installation)
- [An OpenAI API key ](https://platform.openai.com/docs/api-reference/api-keys)

## Install and configure Vectorizer CLI

To be able to run vectorizers in your self-hosted database:

1. **Install [pgai](https://pypi.org/project/pgai/) from PyPI**

   ```bash
   pip install pgai
   ```

   The Vectorizer worker, `vectorizer` is now in your `$PATH`.

1. **Run the vectorizer worker**

   1. Set the connection string to your self-hosted database and the API key for the external embeddings
      provider as environment variables:
   
      ```bash
      export VECTORIZER_DB_URL="postgres://user:password@host:port/dbname"
      export OPENAI_API_KEY="Your OpenAI API key"
      ```
 
   1. Run the vectorizer worker:

      ```bash
      vectorizer
      ```
   
   You can also use the `-d` or `--db-url` arguments to set a Postgres connection string:
   ```bash
   vectorizer -d "postgres://user:password@host:port/dbname"
   ```

## Run vectorizers workers from Vectorizer CLI

By default, when you run a vectorizer worker, it loops over the vectorizers defined in 
your database and processes each vectorizer in turn. Five minutes after completing each 
vectorizer run, the vectorizer worker loops over the vectorizers again. You can also use the 
`-i` / `--vectorizer-id` command line argument to manage which vectorizers that are run by that
worker instance. A vectorizer worker can:

- Run a single vectorizer:

  To run the vectorizer with id 42:
  ```bash
  vectorizer -i 42
  ```

- Run multiple specific vectorizers: 

  To run the vectorizers with ids `42`, `64`, and `8`:

  ```bash
  vectorizer -i 42 -i 64 -i 8
  ```

- Run multiple vectorizers in concurrent vectorizer workers:

  To run the vectorizers with id `42` and `64` in different vectorizer workers:
  1. In a first shell, run:

     ```bash
     vectorizer -id 42
     ```

  1. In another shell, run: 

     ```bash
     vectorizer -id 64
     ```

- Run concurrent vectorizer workers on a single vectorizer

  More than one vectorizer worker can efficiently process the same vectorizer id
  at the same time. To run the vectorizer with id `41` in different vectorizer workers:

  1. In a first shell, run:
  
     ```bash
     vectorizer -id 42
     ```

  1. In another shell, run:

     ```bash
     vectorizer -id 42
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
  vectorizer --poll-interval=1h
  ```

- Run every 45 minutes:

  ```bash
  vectorizer --poll-interval=45m
  ```

- Run every 900 seconds:

  ```bash
  vectorizer --poll-interval=900
  ```

- Run once and then exit: 

  ```bash
  vectorizer --once
  ```
  This is useful if you want to run the vectorizer worker on a cron job.

### Set the number of asynchronous tasks running in a vectorizer worker

Use the `-c` / `--concurrency` option to cause the vectorizer worker to use 
multiple asynchronous tasks to process a queue:

```bash
vectorizer -c 3
```

[python3]: https://www.python.org/downloads/
[pip]: https://pip.pypa.io/en/stable/
