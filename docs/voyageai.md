# Use pgai with Voyage AI

This page shows you how to:

- [Configure pgai for Voyage AI](#configure-pgai-for-voyage-ai)
- [Add AI functionality to your database](#usage)

## Configure pgai for Voyage AI

To use the Voyage AI functions, you need a [Voyage AI API key](https://docs.voyageai.com/docs/api-key-and-installation#authentication-with-api-keys).

In production, we suggest setting the API key using an environment variable.
During testing and development, it may be easiest to configure the key value
as a [session level parameter]. For more options and details, consult the
[Handling API keys](./handling-api-keys.md) document.

[session level parameter]: https://www.postgresql.org/docs/current/config-setting.html#CONFIG-SETTING-SHELL

1. Set your Voyage key as an environment variable in your shell:
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


