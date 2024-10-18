
# Self-hosting Vectorizer

The vectorizer CLI worker asynchronously processes the Vectorizers defined in 
your database.

Vectorizer workers are available on [Timescale Cloud][timescale-cloud]. You can
also self-host it. This guide will help you run the Vectorizer worker on your
own.

## Installation

To self-host the vectorizer, you will need to install the 
[pgai package](https://pypi.org/project/pgai/) from PyPI.

```bash
pip install pgai
```

At this point, `vectorizer` will be on your PATH.

## Connecting to your database

Vectorizer needs to know how to connect to your database. You can specify a
Postgres [connection string](https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING) by

- using the `-d` or `--db-url` command line argument
  ```bash
  vectorizer -d "postgres://user:password@host:port/dbname"
  ```
- using the `VECTORIZER_DB_URL` environment variable
  ```bash
  export VECTORIZER_DB_URL="postgres://user:password@host:port/dbname"
  vectorizer
  ```

The connection string will default to `postgres://postgres@localhost:5432/postgres` if not specified.


## API Keys

Vectorizers use external embedding providers like OpenAI to generate embeddings.
These typically require an API key. Each vectorizer defined in the database will
specify the name of an API key in the `embedding` section of the Vectorizer
configuration. The default, names of the API keys try to match the embedding
provider's default name. For example, for OpenAI, the default name is
`OPENAI_API_KEY`.

You need to set an environment variable that is the same as the API key name
defined in the vectorizer. For example, if your API key name is `OPENAI_API_KEY`
, you need to set the `OPENAI_API_KEY` environment variable to your OpenAI API
key.

```bash
export OPENAI_API_KEY="not-a-real-key"
vectorizer
```

## Choosing Vectorizers to process

By default, the vectorizer worker will loop over all the vectorizers defined in 
the database and process each one. If only want to process one vectorizer use 
the `-i` / `--vectorizer-id` command line argument to pass the id of the
vectorizer you want.

You can look up the ids for vectorizers in the `ai.vectorizer` table.

To run the vectorizer worker on only the vectorizer with id 42, run this:

```bash
vectorizer -i 42
```

In fact, the `-i` / `--vectorizer-id` argument can be specified multiple times.
To run the vectorizer worker against vectorizers 42, 64, and 8, run this:

```bash
vectorizer -i 42 -i 64 -i 8
```

## Modes of operation

When run, the vectorizer will loop over the vectorizers defined in the database.
For each vectorizer, it will process the respective queue until it is empty. By 
default, the vectorizer will then sleep for five minutes and start over.

To change how long it should sleep between iterations, use the `--poll-interval`
command line argument. You can use integer seconds or a duration string.

**Examples:**

```bash
vectorizer --poll-interval=1h
```

```bash
vectorizer --poll-interval=45m
```

```bash
vectorizer --poll-interval=900
```

If you want the vectorizer to only run once and then exit, pass the `--once` 
flag. This is useful if you want to run the vectorizer worker on a cron job.

```bash
vectorizer --once
```

## Concurrency

### Multiple workers on different vectorizers

You can run multiple instances of the vectorizer worker against the same 
database processing different vectorizer ids.

Run this in one shell

```bash
vectorizer -id 42
```

And this in another

```bash
vectorizer -id 64
```

### Multiple workers on the same vectorizer

More than one vectorizer worker can efficiently process the same vectorizer id 
at the same time.

Run this in one shell

```bash
vectorizer -id 42
```

And this in another

```bash
vectorizer -id 42
```

You now have two vectorizer workers processing the vectorizer with id 42.

### Multiple asynchronous tasks within one vectorizer

Use the `-c` / `--concurrency` option to cause the vectorizer worker to use 
multiple asynchronous tasks to process a queue.

```bash
vectorizer -c 3
```
