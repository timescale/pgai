# Handling API keys

A number of pgai functions call out to third-party APIs which require an API
key for authentication. There are a few ways to pass your API key to these
functions. This document lays out the different options and provides
recommendations for which option to use.

API keys are sensitive values, so we provide several ways to specify them so
they can be provided securely:

**Recommended ways (most secure)**

1. If you are using Timescale Cloud, we recommend that you [configure an API key in Timescale Cloud](#configure-an-api-key-in-timescale-cloud).
2. If you are self-hosting, you can [configure an API key through an environment variable available to the PostgreSQL process](#configure-an-api-key-through-an-environment-variable-available-to-the-postgres-process-self-hosted)

**Other ways**
1. You can [configure the api key for an interactive a psql session](#configure-an-api-key-for-an-interactive-psql-session).
2. You can [provide the api key directly with the `api_key` function parameter](#provide-the-api-key-directly-with-the-api_key-function-parameter).

When you call a pgai function without setting `api_key` or `api_key_name`, pgai
attempts to resolve the secret by using a default value for `api_key_name`. The
default is provider-dependent:

| Provider  | Default `api_key_name` |
|-----------|------------------------|
| Anthropic | ANTHROPIC_API_KEY      |
| Cohere    | COHERE_API_KEY         |
| OpenAI    | OPENAI_API_KEY         |
| VoyageAI  | VOYAGE_API_KEY         |


## Configure an API key in Timescale Cloud

1. Navigate to the "AI Model API Keys" tab under "Project settings"

   ![Timescale Cloud project settings](/docs/images/timescale_project_settings.png)

1. Add a new AI Model API key, providing the name and API key

   ![Timescale Cloud new AI model API key](/docs/images/timescale_new_ai_model_api_key.png)

1. Use this API key name in calls to pgai functions, like so:
    ```sql
    SELECT * FROM ai.openai_list_models(api_key_name => 'MY_API_KEY');
    ```

## Configure an API key through an environment variable available to the Postgres process (self-hosted)

If you're running PostgreSQL yourself, or have the ability to configure the
runtime of PostgreSQL, you set an environment variable for the PostgreSQL
process.

### Configure the environment variable

How you configured the environment variable depends on how you are running your
database. Some common examples are: Systemd, Docker, or Docker Compose.

#### Configure the environment variable in Systemd unit

In the `[Service]` stanza of the Systemd unit, you add:

```
Environment=MY_API_KEY=<api key here>
```

#### Configure the environment variable with Docker

You set the environment variable with the `-e` parameter to `docker run`:

```sh
docker run -e MY_API_KEY=<api key here> ... timescale/timescaledb-ha:pg17
```

#### Configure the environment variable with Docker Compose

You set the environment variable in the `environment` parameter of your
database:

```yaml
name: pgai
services:
  db:
    image: timescale/timescaledb-ha:pg17
    environment:
      MY_API_KEY: <api key here>
    ...
```

### Use the name of the environment variable in calls to pgai

```sql
SELECT * FROM ai.openai_list_models(api_key_name => 'MY_API_KEY');
```

## Configure an API key for an interactive psql session

To use a [session level parameter when connecting to your database with psql](https://www.postgresql.org/docs/current/config-setting.html#CONFIG-SETTING-SHELL)
to run your AI queries:

1. Set the api key as an environment variable in your shell:
    ```bash
    export MY_API_KEY="this-is-my-super-secret-api-key-dont-tell"
    ```

1. Use the session-level parameter when you connect to your database:

    ```bash
    PGOPTIONS="-c ai.my_api_key=$MY_API_KEY" psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>"
    ```

1. Run your AI query:

    ```sql
    SELECT * FROM ai.voyageai_embed('voyage-3-lite', 'sample text to embed', api_key_name => 'my_api_key');
    ```


## provide the api key directly with the `api_key` function parameter

Note: passing the `api_key` parameter to a pgai function as text results in the
value being printed into the PostgreSQL logs. This could expose your API key.
Instead, we recommend passing the `api_key` parameter as a bind variable:

1. Set the API key as an environment variable in your shell:
    ```bash
    export MY_API_KEY="this-is-my-super-secret-api-key-dont-tell"
    ```

2. Connect to your database and set your api key as a [psql variable](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-VARIABLES):

      ```bash
      psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>" -v my_api_key=$MY_API_KEY
      ```
   Your API key is now available as a psql variable named `my_api_key` in your psql session.

   You can also log into the database, then set `my_api_key` using the `\getenv` [metacommand](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-META-COMMAND-GETENV):

      ```sql
      \getenv my_api_key MY_API_KEY
      ```

3. Pass your API key to your parameterized query:
    ```sql
    SELECT *
    FROM ai.openai_list_models(api_key=>$1)
    ORDER BY created DESC
    \bind :my_api_key
    \g
    ```
