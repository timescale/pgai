# Use pgai with Voyage AI

This page shows you how to:

- [Configure pgai for Voyage AI](#configure-pgai-for-voyage-ai)
- [Add AI functionality to your database](#usage)
- [Follow advanced AI examples](#advanced-examples)

## Configure pgai for Voyage AI

To use the Voyage AI functions, you need a [Voyage AI API key](https://docs.voyageai.com/docs/api-key-and-installation#authentication-with-api-keys).

- [Handle API keys using pgai from psql](#handle-api-keys-using-pgai-from-psql)
- [Handle API keys using pgai from python](#handle-api-keys-using-pgai-from-python)

### Handle API keys using pgai from psql

The api key is an [optional parameter to pgai functions](https://www.postgresql.org/docs/current/sql-syntax-calling-funcs.html).
You can either:

* [Run AI queries by passing your API key implicitly as a session parameter](#run-ai-queries-by-passing-your-api-key-implicitly-as-a-session-parameter)
* [Run AI queries by passing your API key explicitly as a function argument](#run-ai-queries-by-passing-your-api-key-explicitly-as-a-function-argument)

#### Run AI queries by passing your API key implicitly as a session parameter

To use a [session level parameter when connecting to your database with psql](https://www.postgresql.org/docs/current/config-setting.html#CONFIG-SETTING-SHELL)
to run your AI queries:

1. Set your Voyage AI key as an environment variable in your shell:
    ```bash
    export VOYAGE_API_KEY="this-is-my-super-secret-api-key-dont-tell"
    ```
1. Use the session level parameter when you connect to your database:

    ```bash
    PGOPTIONS="-c ai.voyage_api_key=$VOYAGE_API_KEY" psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>"
    ```

1. Run your AI query:

   `ai.voyage_api_key` is set for the duration of your psql session, you do not need to specify it for pgai functions.

    ```sql
    SELECT * FROM ai.voyageai_embed('voyage-3-lite', 'sample text to embed');
    ```

#### Run AI queries by passing your API key explicitly as a function argument

1. Set your Voyage AI key as an environment variable in your shell:
    ```bash
    export VOYAGE_API_KEY="this-is-my-super-secret-api-key-dont-tell"
    ```

2. Connect to your database and set your api key as a [psql variable](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-VARIABLES):

      ```bash
      psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>" -v voyage_api_key=$VOYAGE_API_KEY
      ```
   Your API key is now available as a psql variable named `voyage_api_key` in your psql session.

   You can also log into the database, then set `voyage_api_key` using the `\getenv` [metacommand](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-META-COMMAND-GETENV):

      ```sql
      \getenv voyage_api_key VOYAGE_API_KEY
      ```

3. Pass your API key to your parameterized query:
    ```sql
    SELECT *
    FROM ai.voyageai_embed('voyage-3-lite', 'sample text to embed', api_key=>$1)
    ORDER BY created DESC
    \bind :voyage_api_key
    \g
    ```

   Use [\bind](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-META-COMMAND-BIND) to pass the value of `voyage_api_key` to the parameterized query.

   The `\bind` metacommand is available in psql version 16+.

4. Once you have used `\getenv` to load the environment variable to a psql variable
   you can optionally set it as a session-level parameter which can then be used explicitly.
   ```sql
   SELECT set_config('ai.voyage_api_key', $1, false) IS NOT NULL
   \bind :voyage_api_key
   \g
   ```

   ```sql
   SELECT * FROM ai.voyageai_embed('voyage-3-lite', 'sample text to embed');
   ```

### Handle API keys using pgai from python

1. In your Python environment, include the dotenv and postgres driver packages:

    ```bash
    pip install python-dotenv
    pip install psycopg2-binary
    ```

1. Set your Voyage AI key in a .env file or as an environment variable:
    ```bash
    VOYAGE_API_KEY="this-is-my-super-secret-api-key-dont-tell"
    DB_URL="your connection string"
    ```

1. Pass your API key as a parameter to your queries:

    ```python
    import os
    from dotenv import load_dotenv

    load_dotenv()

    VOYAGE_API_KEY = os.environ["VOYAGE_API_KEY"]
    DB_URL = os.environ["DB_URL"]

    import psycopg2

    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            # pass the API key as a parameter to the query. don't use string manipulations
            cur.execute("SELECT * FROM ai.voyageai_embed('voyage-3-lite', 'sample text to embed', api_key=>%s)", (VOYAGE_API_KEY,))
            records = cur.fetchall()
    ```

   Do not use string manipulation to embed the key as a literal in the SQL query.


## Usage

This section shows you how to use AI directly from your database using SQL.

- [Embed](#embed): generate [embeddings](https://docs.voyageai.com/docs/embeddings) using a
  specified model.

### Embed

Generate [embeddings](https://docs.voyageai.com/docs/embeddings) using a specified model.

- Request an embedding using a specific model:

    ```sql
    SELECT ai.voyageai_embed
    ( 'voyage-3-lite'
    , 'the purple elephant sits on a red mushroom'
    );
    ```

  The data returned looks like:

    ```text
                          voyageai_embed                      
    --------------------------------------------------------
     [0.005978798,-0.020522336,...-0.0022857306,-0.023699166]
    (1 row)
    ```

- Pass an array of text inputs:

    ```sql
    SELECT ai.voyageai_embed
    ( 'voyage-3-lite'
    , array['Timescale is Postgres made Powerful', 'the purple elephant sits on a red mushroom']
    );
    ```
  
- Specify the input type

  The Voyage AI API allows setting the `input_type` to `"document"`, or
  `"query"`, (or unset). Correctly setting this value should enhance retrieval
  quality:

    ```sql
    SELECT ai.voyageai_embed
    ( 'voyage-3-lite'
    , 'A query'
    , input_type => 'query'
    );
    ```


