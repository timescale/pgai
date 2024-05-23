# pgai

Artificial intelligence for Postgres.

## Handling API Tokens

API keys are secrets. Exposing them can present financial and/or information
security issues. Below are some non-exhaustive tips to help protect your 
keys.

### psql

```bash
OPENAI_AI_KEY="sk-this-is-my-super-secret-api-key-dont-tell"
```

Assuming you have your OPENAI_API_KEY in an environment variable, you can set
a [psql variable](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-VARIABLES) to the value of the key when connecting to the database with a
[command line argument](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-OPTION-VARIABLE) like so:

```bash
psql -v OPENAI_API_KEY=$OPENAI_API_KEY
```

Using a colon followed by a psql variable name will [substitute](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-INTERPOLATION) the variable's 
value into a query. If you want the variable's value to be treated as text, 
wrap the variable name in single quotes.

```sql
-- DON'T DO THIS! The results will show your key in plain text.
SELECT :'OPENAI_API_KEY';
```

You can use this technique to pass your API key as a text literal to a function 
as an argument without displaying your plain text key in the raw SQL.

```sql
SELECT * 
FROM openai_list_models(:'OPENAI_API_KEY')
ORDER BY created DESC;
```

Unfortunately, since the key is being provided as a text literal, it could show 
up in logs, pg_stat_statements, etc. To take our precautions one step further, 
make the query parameterized ($1) and [bind](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-META-COMMAND-BIND) the psql variable's value to the 
parameter using the `\bind` metacommand. Note that we don't wrap the variable
name in single quotes using this technique. `\g` causes psql to execute the
query.

The `\bind` metacommand is available in psql version 16+.

```sql
SELECT * 
FROM openai_list_models($1)
ORDER BY created DESC
\bind :OPENAI_API_KEY
\g
```

### Python

The [dotenv](https://github.com/theskumar/python-dotenv) is frequently used to 
load API tokens, passwords, connection strings, and other configuration 
settings from a .env file.

```bash
pip install python-dotenv
pip install psycopg2-binary
```

Be sure to pass the API key as a parameter to your queries. Don't use string 
manipulation techniques to embed the key as a literal in the SQL query.

```python
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
DB_URL = os.environ["DB_URL"]

import psycopg2

with psycopg2.connect(DB_URL) as conn:
    with conn.cursor() as cur:
        # pass the API key as a parameter to the query. don't use string manipulations
        cur.execute("SELECT * FROM openai_list_models(%s) ORDER BY created DESC", (OPENAI_API_KEY,))
        records = cur.fetchall()
```

## Usage

### List Models

To list the models supported in the OpenAI functions, call the 
`open_ai_list_models` function. It returns a table

```sql
SELECT * 
FROM openai_list_models($1)
ORDER BY created DESC
\bind :OPENAI_API_KEY
\g
```

```text
             id              |        created         |    owned_by     
-----------------------------+------------------------+-----------------
 gpt-4o-test-shared          | 2024-05-20 13:06:56-05 | system
 gpt-4o-2024-05-13           | 2024-05-10 14:08:52-05 | system
 gpt-4o                      | 2024-05-10 13:50:49-05 | system
 gpt-4-turbo-2024-04-09      | 2024-04-08 13:41:17-05 | system
 gpt-4-turbo                 | 2024-04-05 18:57:21-05 | system
 gpt-4-1106-vision-preview   | 2024-03-26 12:10:33-05 | system
 gpt-3.5-turbo-0125          | 2024-01-23 16:19:18-06 | system
 gpt-4-turbo-preview         | 2024-01-23 13:22:57-06 | system
 gpt-4-0125-preview          | 2024-01-23 13:20:12-06 | system
 text-embedding-3-large      | 2024-01-22 13:53:00-06 | system
 text-embedding-3-small      | 2024-01-22 12:43:17-06 | system
 tts-1-hd-1106               | 2023-11-03 18:18:53-05 | system
 tts-1-1106                  | 2023-11-03 18:14:01-05 | system
 tts-1-hd                    | 2023-11-03 16:13:35-05 | system
 gpt-3.5-turbo-1106          | 2023-11-02 16:15:48-05 | system
 gpt-4-1106-preview          | 2023-11-02 15:33:26-05 | system
 gpt-4-vision-preview        | 2023-11-01 22:15:17-05 | system
 dall-e-2                    | 2023-10-31 19:22:57-05 | system
 dall-e-3                    | 2023-10-31 15:46:29-05 | system
 gpt-3.5-turbo-instruct-0914 | 2023-09-07 16:34:32-05 | system
 gpt-3.5-turbo-instruct      | 2023-08-24 13:23:47-05 | system
 babbage-002                 | 2023-08-21 11:16:55-05 | system
 davinci-002                 | 2023-08-21 11:11:41-05 | system
 gpt-4                       | 2023-06-27 11:13:31-05 | openai
 gpt-4-0613                  | 2023-06-12 11:54:56-05 | openai
 gpt-3.5-turbo-0613          | 2023-06-12 11:30:34-05 | openai
 gpt-3.5-turbo-16k-0613      | 2023-05-30 14:17:27-05 | openai
 gpt-3.5-turbo-16k           | 2023-05-10 17:35:02-05 | openai-internal
 tts-1                       | 2023-04-19 16:49:11-05 | openai-internal
 gpt-3.5-turbo-0301          | 2023-02-28 23:52:43-06 | openai
 gpt-3.5-turbo               | 2023-02-28 12:56:42-06 | openai
 whisper-1                   | 2023-02-27 15:13:04-06 | openai-internal
 text-embedding-ada-002      | 2022-12-16 13:01:39-06 | openai-internal
(33 rows)
```

### Tokenization

Encode content into an array of tokens with `openai_tokenize`.

```sql
SELECT openai_tokenize
( 'text-embedding-ada-002'
, 'Timescale is Postgres made Powerful'
);
```

```text
            openai_tokenize             
----------------------------------------
 {19422,2296,374,3962,18297,1903,75458}
(1 row)
```

Count tokens using `array_length` on the token array.

```sql
SELECT array_length
( openai_tokenize
  ( 'text-embedding-ada-002'
  , 'Timescale is Postgres made Powerful'
  )
, 1
);
```

```text
 array_length 
--------------
            7
(1 row)
```

### Detokenization

Turn tokenized content back into natural language with the `openai_detokenize` function.

```sql
SELECT openai_detokenize('text-embedding-ada-002', array[1820,25977,46840,23874,389,264,2579,58466]);
```

```text
             openai_detokenize              
--------------------------------------------
 the purple elephant sits on a red mushroom
(1 row)
```

### Embeddings

You can generate embeddings using a specified model.

```sql
SELECT openai_embed
( $1
, 'text-embedding-ada-002'
, 'the purple elephant sits on a red mushroom'
)
\bind :OPENAI_API_KEY
\g
```

Truncated output...

```text
                      openai_embed                      
--------------------------------------------------------
 [0.005978798,-0.020522336,...-0.0022857306,-0.023699166]
(1 row)
```

Some models support specifying the number of dimensions you want in the 
returned embedding.

```sql
SELECT openai_embed
( $1
, 'text-embedding-ada-002'
, 'the purple elephant sits on a red mushroom'
, _dimensions=>768
)
\bind :OPENAI_API_KEY
\g
```

You may optionally pass a user identifier.

```sql
SELECT openai_embed
( $1
, 'text-embedding-ada-002'
, 'the purple elephant sits on a red mushroom'
, _user=>'bac1aaf7-4460-42d3-bba5-2957b057f4a5'
)
\bind :OPENAI_API_KEY
\g
```

You may pass an array of text inputs.

```sql
SELECT openai_embed
( $1
, 'text-embedding-ada-002'
, array['Timescale is Postgres made Powerful', 'the purple elephant sits on a red mushroom']
)
\bind :OPENAI_API_KEY
\g
```

You may also provide a tokenized input.

```sql
select openai_embed
( $1
, 'text-embedding-ada-002'
, array[1820,25977,46840,23874,389,264,2579,58466]
)
\bind :OPENAI_API_KEY
\g
```

### Text Generation / Chat Completion

You can do text generation / chat completion using the `openai_chat_complete` 
function.

```sql
\pset tuples_only on
\pset format unaligned

SELECT jsonb_pretty
(
  openai_chat_complete
  ( $1
  , 'gpt-4o'
  , jsonb_build_array
    ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
    , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
    )
  )
)
\bind :OPENAI_API_KEY
\g
```

```json
{
    "id": "chatcmpl-9RgehyQ0aydAkQajrN6Oe0lepERKC",
    "model": "gpt-4o-2024-05-13",
    "usage": {
        "total_tokens": 332,
        "prompt_tokens": 26,
        "completion_tokens": 306
    },
    "object": "chat.completion",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "In Alabama, June typically ushers in the summer season with warm to hot temperatures and relatively high humidity. Here’s a general overview of what you can expect:\n\n1. **Temperature**: \n   - Average daytime highs usually range from the mid-80s to low 90s Fahrenheit (around 29-35°C).\n   - Nighttime temperatures often fall to the mid-60s to mid-70s Fahrenheit (18-24°C).\n\n2. **Humidity**:\n   - Humidity levels can be quite high, making the temperatures feel even warmer. The mix of heat and humidity can lead to a muggy atmosphere.\n\n3. **Rainfall**:\n   - June is part of the wet season for Alabama, so you can expect a fair amount of rainfall. Thunderstorms are relatively common, often in the afternoons and evenings.\n   - The precipitation can be sporadic, with sudden downpours that can clear up quickly.\n\n4. **Sunshine**:\n   - There are plenty of sunny days, though the sunshine can be intense. Ultraviolet (UV) levels are high, so sun protection is important.\n\n5. **Overall Climate**:\n   - Generally, the climate in Alabama in June is characterized by a typical Southeastern U.S. summer: hot, humid, and occasionally stormy. \n\nIf you’re planning a visit or activities in Alabama during June, it’s a good idea to stay hydrated, wear light clothing, and keep an eye on the weather forecast for any potential thunderstorms."
            },
            "logprobs": null,
            "finish_reason": "stop"
        }
    ],
    "created": 1716385851,
    "system_fingerprint": "fp_729ea513f7"
}
```

The `openai_chat_complete` function returns a jsonb object containing the
response from the API. You can use jsonb operators and functions to manipulate
the object. The following returns the content as text from the first message
in the choices array.

```sql
\pset tuples_only on
\pset format unaligned

select openai_chat_complete
( 'gpt-4o'
, :'OPENAI_API_KEY'
, jsonb_build_array
  ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
  , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
  )
)->'choices'->0->'message'->>'content'
;
```

```text
In June, Alabama generally experiences warm to hot weather as it transitions into summer. Typical conditions include:

1. **Temperatures**: Daytime highs usually range from the mid-80s to low 90s Fahrenheit (around 29-34°C). Nighttime lows typically range from the mid-60s to low 70s Fahrenheit (around 18-23°C).

2. **Humidity**: June tends to be quite humid, which can make the temperatures feel even warmer. High humidity levels are characteristic of Alabama summers.

3. **Precipitation**: June is part of the wetter season in Alabama, with regular afternoon thunderstorms being common. Rainfall can vary, but you can expect an average of about 4 to 5 inches (around 100-125 mm) of rain for the month.

4. **Sunshine**: There are usually plenty of sunny days, although the frequent thunderstorms can lead to overcast skies at times.

Overall, if you're planning to visit Alabama in June, be prepared for hot and humid conditions, and keep an umbrella or rain jacket handy for those afternoon storms.
```

### Moderation

Classify content as potentially harmful by using the `openai_moderate` 
function.

```sql
\pset tuples_only on
\pset format unaligned

select jsonb_pretty
(
  openai_moderate
  ( $1
  , 'text-moderation-stable'
  , 'I want to kill them.'
  )
)
\bind :OPENAI_API_KEY
\g
```

```text
{
    "id": "modr-9RsN6qZWoZYm1AK4mtrKuEjfOcMWp",
    "model": "text-moderation-007",
    "results": [
        {
            "flagged": true,
            "categories": {
                "hate": false,
                "sexual": false,
                "violence": true,
                "self-harm": false,
                "self_harm": false,
                "harassment": true,
                "sexual/minors": false,
                "sexual_minors": false,
                "hate/threatening": false,
                "hate_threatening": false,
                "self-harm/intent": false,
                "self_harm_intent": false,
                "violence/graphic": false,
                "violence_graphic": false,
                "harassment/threatening": true,
                "harassment_threatening": true,
                "self-harm/instructions": false,
                "self_harm_instructions": false
            },
            "category_scores": {
                "hate": 0.2324090600013733,
                "sexual": 0.00001205232911161147,
                "violence": 0.997192919254303,
                "self-harm": 0.0000023696395601291442,
                "self_harm": 0.0000023696395601291442,
                "harassment": 0.5278584957122803,
                "sexual/minors": 0.00000007506431387582779,
                "sexual_minors": 0.00000007506431387582779,
                "hate/threatening": 0.024183575063943863,
                "hate_threatening": 0.024183575063943863,
                "self-harm/intent": 0.0000017161115692942985,
                "self_harm_intent": 0.0000017161115692942985,
                "violence/graphic": 0.00003399916022317484,
                "violence_graphic": 0.00003399916022317484,
                "harassment/threatening": 0.5712487697601318,
                "harassment_threatening": 0.5712487697601318,
                "self-harm/instructions": 0.000000001132860139030356,
                "self_harm_instructions": 0.000000001132860139030356
            }
        }
    ]
}
```

## Docker

### Building the image

```bash
docker build -t pgai .
```

### Running the container

```bash
docker run -d --name pgai -p 9876:5432 -e POSTGRES_PASSWORD=pgaipass pgai
```

### Connecting to the database

```bash
psql -d "postgres://postgres:pgaipass@localhost:9876/postgres"
```

### Creating the extension

```sql
CREATE EXTENSION ai CASCADE;
```

## Prerequisites

1. PostgreSQL (obviously) version 16
2. [plpython3u](https://www.postgresql.org/docs/current/plpython.html)
3. [pgvector](https://github.com/pgvector/pgvector)
4. Python3 with the following packages
    1. [openai](https://pypi.org/project/openai/)
    2. [tiktoken](https://pypi.org/project/tiktoken/)

## Installation

Using docker is recommended, however a Makefile is provided if you wish to 
install the extension on your system. The `install` make target will download 
and install the pgvector extension, install the pgai extension, and install 
the Python package dependencies in your system's Python environment.

```bash
make install
```

## Create Extension

After installation, the extension must be created in a Postgres database. Since
the extension depends on both plpython3u and pgvector, using the `CASCADE` 
option is recommended to automatically install them if they are not already.

```sql
CREATE EXTENSION IF NOT EXISTS ai CASCADE;
```

Alternately, you can use the `create_extension` make target. Be aware that the
`DB` and `USER` make variables are used to establish a connection to the 
running database, so modify them accordingly if needed.

```bash
make create_extension
```
