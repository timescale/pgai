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
    , _api_key=>$1
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
                , _api_key=>%s
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
