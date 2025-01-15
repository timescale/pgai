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


