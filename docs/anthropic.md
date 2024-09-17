# Use pgai with Anthropic

This page shows you how to:

- [Configure pgai for Anthropic](#configure-pgai-for-anthropic)
- [Add AI functionality to your database](#usage)

## Configure pgai for Anthropic

Anthropic functions in pgai require an [Anthropic API key](https://docs.anthropic.com/en/docs/quickstart#set-your-api-key).

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

1. Set your Anthropic key as an environment variable in your shell:
    ```bash
    export ANTHROPIC_API_KEY="this-is-my-super-secret-api-key-dont-tell"
    ```
1. Use the session level parameter when you connect to your database:

    ```bash
    PGOPTIONS="-c ai.anthropic_api_key=$ANTHROPIC_API_KEY" psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>"
    ```

1. Run your AI query:

   `ai.anthropic_api_key` is set for the duration of your psql session, you do not need to specify it for pgai functions.

    ```sql
    select ai.anthropic_generate
    ( 'claude-3-5-sonnet-20240620'
    , jsonb_build_array
      ( jsonb_build_object
        ( 'role', 'user'
        , 'content', 'Name five famous people from Birmingham, Alabama.'
        )
      )
    );
    ```

#### Run AI queries by passing your API key explicitly as a function argument

1. Set your Anthropic key as an environment variable in your shell:
    ```bash
    export ANTHROPIC_API_KEY="this-is-my-super-secret-api-key-dont-tell"
    ```

2. Connect to your database and set your api key as a [psql variable](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-VARIABLES):

      ```bash
      psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>" -v anthropic_api_key=$ANTHROPIC_API_KEY
      ```
   Your API key is now available as a psql variable named `anthropic_api_key` in your psql session.

   You can also log into the database, then set `anthropic_api_key` using the `\getenv` [metacommand](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-META-COMMAND-GETENV):

      ```sql
       \getenv anthropic_api_key ANTHROPIC_API_KEY
      ```

4. Pass your API key to your parameterized query:
    ```sql
    SELECT ai.anthropic_generate
    ( 'claude-3-5-sonnet-20240620'
    , jsonb_build_array
      ( jsonb_build_object
        ( 'role', 'user'
        , 'content', 'Name five famous people from Birmingham, Alabama.'
        )
      )
    , api_key=>$1
    ) AS actual
    \bind :anthropic_api_key
    \g
    ```

   Use [\bind](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-META-COMMAND-BIND) to pass the value of `anthropic_api_key` to the parameterized query.

   The `\bind` metacommand is available in psql version 16+.

### Handle API keys using pgai from python

1. In your Python environment, include the dotenv and postgres driver packages:

    ```bash
    pip install python-dotenv
    pip install psycopg2-binary
    ```

2. Set your Anthropic API key in a .env file or as an environment variable:
    ```bash
    ANTHROPIC_API_KEY="this-is-my-super-secret-api-key-dont-tell"
    DB_URL="your connection string"
    ```

3. Pass your API key as a parameter to your queries:

    ```python
    import os
    from dotenv import load_dotenv
        
    load_dotenv()
       
    ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
    DB_URL = os.environ["DB_URL"]
       
    import psycopg2
    from psycopg2.extras import Json
       
    messages = [{'role': 'user', 'content': 'Name five famous people from Birmingham, Alabama.'}]
       
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            # pass the API key as a parameter to the query. don't use string manipulations
            cur.execute("""
                SELECT ai.anthropic_generate
                ( 'claude-3-5-sonnet-20240620'
                , %s
                , api_key=>%s
                )
            """, (Json(messages), ANTHROPIC_API_KEY))
            records = cur.fetchall()
    ```

   Do not use string manipulation to embed the key as a literal in the SQL query.

## Usage

This section shows you how to use AI directly from your database using SQL.

- [Generate](#generate): generate a response to a prompt

### Generate

[Generate a response for the prompt provided](https://docs.anthropic.com/en/api/messages):

```sql
-- the following two metacommands cause the raw query results to be printed
-- without any decoration
\pset tuples_only on
\pset format unaligned

select jsonb_extract_path_text
(
   ai.anthropic_generate
   ( 'claude-3-5-sonnet-20240620'
   , jsonb_build_array
     ( jsonb_build_object
       ( 'role', 'user'
       , 'content', 'Name five famous people from Birmingham, Alabama.'
       )
     )
   )
, 'content', '0', 'text'
);
```

The data returned looks like:

```text
Here are five famous people from Birmingham, Alabama:

1. Condoleezza Rice - Former U.S. Secretary of State and National Security Advisor

2. Courteney Cox - Actress, best known for her role as Monica Geller on the TV show "Friends"

3. Charles Barkley - Former NBA player and current television analyst

4. Vonetta Flowers - Olympic gold medalist in bobsledding, the first African American to win a gold medal at the Winter Olympics

5. Carl Lewis - Olympic track and field athlete who won nine gold medals across four Olympic Games

These individuals have made significant contributions in various fields, including politics, entertainment, sports, and athletics, and have helped put Birmingham, Alabama on the map in their respective areas.
```

## Tools Use

Here is a [tool_use](https://github.com/anthropics/anthropic-cookbook/tree/main/tool_use)
example which you can also delegate specific tasks on your data to the AI.

```sql
\getenv anthropic_api_key ANTHROPIC_API_KEY

SELECT jsonb_pretty(ai.anthropic_generate
( 'claude-3-5-sonnet-20240620'
, jsonb_build_array(
    jsonb_build_object(
      'role', 'user',
      'content', 'John works at Google in New York. He met with Sarah, the CEO of Acme Inc., last week in San Francisco.'
    )
  )
, _max_tokens => 4096
, _api_key => $1
, _tools => jsonb_build_array(
    jsonb_build_object(
      'name', 'print_entities',
      'description', 'Prints extract named entities.',
      'input_schema', jsonb_build_object(
        'type', 'object',
        'properties', jsonb_build_object(
          'entities', jsonb_build_object(
            'type', 'array',
            'items', jsonb_build_object(
              'type', 'object',
              'properties', jsonb_build_object(
                'name', jsonb_build_object('type', 'string', 'description', 'The extracted entity name.'),
                'type', jsonb_build_object('type', 'string', 'description', 'The entity type (e.g., PERSON, ORGANIZATION, LOCATION).'),
                'context', jsonb_build_object('type', 'string', 'description', 'The context in which the entity appears in the text.')
              ),
              'required', jsonb_build_array('name', 'type', 'context')
            )
          )
        ),
        'required', jsonb_build_array('entities')
      )
    )
  )
)::jsonb) AS result
\bind :anthropic_api_key
\g
```

Outputs:

```json
{
    "id": "msg_013VZ3M65KQy8pnh2664YLPA",
    "role": "assistant",
    "type": "message",
    "model": "claude-3-5-sonnet-20240620",
    "usage": {
        "input_tokens": 498,
        "output_tokens": 346
    },
    "content": [
        {
            "text": "Certainly! I'll use the print_entities tool to extract the named entities from the given document. Let's proceed with the function call:",
            "type": "text"
        },
        {
            "id": "toolu_0114pK4oBxD53xdfgEBrgq73",
            "name": "print_entities",
            "type": "tool_use",
            "input": {
                "entities": [
                    {
                        "name": "John",
                        "type": "PERSON",
                        "context": "John works at Google in New York."
                    },
                    {
                        "name": "Google",
                        "type": "ORGANIZATION",
                        "context": "John works at Google in New York."
                    },
                    {
                        "name": "New York",
                        "type": "LOCATION",
                        "context": "John works at Google in New York."
                    },
                    {
                        "name": "Sarah",
                        "type": "PERSON",
                        "context": "He met with Sarah, the CEO of Acme Inc., last week in San Francisco."
                    },
                    {
                        "name": "Acme Inc.",
                        "type": "ORGANIZATION",
                        "context": "He met with Sarah, the CEO of Acme Inc., last week in San Francisco."
                    },
                    {
                        "name": "San Francisco",
                        "type": "LOCATION",
                        "context": "He met with Sarah, the CEO of Acme Inc., last week in San Francisco."
                    }
                ]
            }
        }
    ],
    "stop_reason": "tool_use",
    "stop_sequence": null
}
```

You can run this example of **tool_use** in your database to extract named
entities from the given text input.
The [extract_entities.sql](../examples/extract_entities.sql) is wrapping the
function.

```sql
 SELECT * FROM detect_entities('John works at Timescale in New York.');
 entity_name | entity_type  |            entity_context
-------------+--------------+--------------------------------------
 John        | PERSON       | John works at Timescale in New York.
 Timescale   | ORGANIZATION | John works at Timescale in New York.
 New York    | LOCATION     | John works at Timescale in New York.
```

With the `anonymize_text` function, you can anonymize the text by replacing
the named entities with their types.

```sql
 SELECT * FROM anonymize_text('John works at Timescale in New York.');
-[ RECORD 1 ]--+------------------------------------------------
anonymize_text | :PERSON: works at :ORGANIZATION: in :LOCATION:.
```
Through the same mechanism, the [summarize_article.sql](../examples/summarize_article.sql)
example shows how to extract structured json with the `summarize_article` tool.

```sql
select * from summarize_article($$
  From URL: https://docs.timescale.com/use-timescale/latest/compression
  #  Compression

  Time-series data can be compressed to reduce the amount of storage required,
  and increase the speed of some queries. This is a cornerstone feature of Timescale.
  When new data is added to your database, it is in the form of uncompressed rows.
  Timescale uses a built-in job scheduler to convert this data to the form of
  compressed columns. This occurs across chunks of Timescale hypertables.

   Timescale charges are based on how much storage you use. You don't pay for a 
   fixed storage size, and you don't need to worry about scaling disk size as your
   data grows; We handle it all for you. To reduce your data costs further, use
   compression, a data retention policy, and tiered storage.

$$);
-[ RECORD 1 ]------------------------------------------------------------------
author     | Timescale Documentation
topics     | {"database management","data compression","time-series data",
           |  "data storage optimization"}
summary    | The article discusses Timescale's compression feature for time-series data.
           | It explains that compression is a key feature of Timescale, designed
           | to reduce storage requirements and improve query performance. The
           | process involves converting newly added uncompressed row data into 
           | compressed columns using a built-in job scheduler. This compression
           | occurs across chunks of Timescale hypertables. The article also 
           | mentions that Timescale's pricing model is based on actual storage
           | used, with automatic scaling. To further reduce data costs, users 
           | are advised to employ compression, implement data retention policies,
           | and utilize tiered storage.
coherence  | 95
persuasion | 0.8
```

