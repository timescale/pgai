
<p></p>
<div align=center>

# pgai

<h3>pgai brings AI workflows to your PostgreSQL database</h3>

[![Discord](https://img.shields.io/badge/Join_us_on_Discord-black?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/QedVDxRb)
[![Try Timescale for free](https://img.shields.io/badge/Try_Timescale_for_free-black?style=for-the-badge&logo=timescale&logoColor=white)](https://tsdb.co/gh-pgai-signup)
</div>

pgai simplifies the process of building [search](https://en.wikipedia.org/wiki/Similarity_search), and 
[Retrieval Augmented Generation](https://en.wikipedia.org/wiki/Prompt_engineering#Retrieval-augmented_generation)(RAG) AI applications with PostgreSQL. 

pgai brings embedding and generation AI models closer to the database. With pgai, you can now do the following directly from within PostgreSQL in a SQL query:

* Create [embeddings](#embed) for your data.
* Retrieve LLM [chat completions](#chat-complete) from models like OpenAI GPT4o and Llama 3.
* Reason over your data and facilitate use cases like [classification, summarization, and data enrichment](docs/advanced.md) on your existing relational data in PostgreSQL.

Here's how to get started with pgai:

* **Everyone**: Use pgai in your PostgreSQL database.
  * [Installation](#installation)
  * [Add AI functionality to your database](#usage).
  * [Advanced AI examples using data](./docs/advanced.md)  
  * [Address provider-specific setup steps](#provider-specific-setup)
* **Extension contributor**: Contribute to pgai and improve the project.
  * [Develop and test changes to the pgai extension](./DEVELOPMENT.md)
  * See the [Issues tab](https://github.com/timescale/pgai/issues) for a list of feature ideas to contribute.

**Learn more about pgai:** To learn more about the pgai extension and why we built it, read this blog post [pgai: Giving PostgreSQL Developers AI Engineering Superpowers](http://www.timescale.com/blog/pgai-giving-postgresql-developers-ai-engineering-superpowers).

## Installation

The fastest ways to run PostgreSQL with the pgai extension are to:

* [Use a pre-built Docker container](#use-a-pre-built-docker-container)
* [Install from source](#install-from-source)
* [Use a Timescale Cloud service](#use-a-timescale-cloud-service)

Then, [enable the pgai extension](#enabling-the-pgai-extension-in-your-database) in your database.

### Use a pre-built Docker container

[Run the TimescaleDB Docker image](https://docs.timescale.com/self-hosted/latest/install/installation-docker/).

### Install from source

You can install pgai from source in an existing PostgreSQL server.
You will need [Python3](https://www.python.org/downloads/) and [pip](https://pip.pypa.io/en/stable/) installed system-wide. 
You will also need to install the [plpython3](https://www.postgresql.org/docs/current/plpython.html) 
and [pgvector](https://github.com/pgvector/pgvector) extensions.
After installing these prerequisites, run:

```bash
make install
```

### Use a Timescale Cloud service

Create a new [Timescale Service](https://console.cloud.timescale.com/dashboard/create_services).

If you want to use an existing service, pgai is added as an available extension on the first maintenance window
after the pgai release date.

### Enabling the pgai extension in your database

1. Connect to your database with a postgres client like [psql v16](https://docs.timescale.com/use-timescale/latest/integrations/query-admin/psql/) 
   or [PopSQL](https://docs.timescale.com/use-timescale/latest/popsql/)
   ```bash
   psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>"
   ```

3. Create the pgai extension:

    ```sql
    CREATE EXTENSION IF NOT EXISTS ai CASCADE;
    ```
   
   The `CASCADE` automatically installs `pgvector` and `plpython3u` extensions.


## Usage

This section shows you how to use AI directly from your database using SQL.

- [List_models](#list-models): list the models supported by OpenAI functions in pgai.
- [Tokenize](#tokenize): encode content into tokens.
- [Detokenize](#detokenize): turn tokens into natural language.
- [Embed](#embed): generate [embeddings](https://platform.openai.com/docs/guides/embeddings) using a
  specified model.
- [Chat_complete](#chat-complete): generate text or complete a chat.
- [Generate](#generate): generate a response to a prompt
- [Moderate](#moderate): check if content is classified as potentially harmful
- [List running models](#list-running-models): list the models currently running

### List models

#### OpenAI list models

List the models supported by OpenAI functions in pgai.

```sql
SELECT * 
FROM openai_list_models()
ORDER BY created DESC
;
```
The data returned looks like:

```text
             id              |        created         |    owned_by     
-----------------------------+------------------------+-----------------
 gpt-4o-test-shared          | 2024-05-20 13:06:56-05 | system
 gpt-4o-2024-05-13           | 2024-05-10 14:08:52-05 | system
 gpt-4o                      | 2024-05-10 13:50:49-05 | system
 gpt-4-turbo-2024-04-09      | 2024-04-08 13:41:17-05 | system
 gpt-4-turbo                 | 2024-04-05 18:57:21-05 | system
 ...
(N rows)
```
#### Ollama list models

List the models supported by Ollama functions in pgai.

```sql
SELECT * 
FROM ollama_list_models()
ORDER BY size DESC
;
```
The data returned will look something like the following but will be different 
depending on the models pulled in your Ollama instance.

```text
     name      |     model     |    size    |                              digest                              | family | format |     families      | parent_model | parameter_size | quantization_level |          modified_at          
---------------+---------------+------------+------------------------------------------------------------------+--------+--------+-------------------+--------------+----------------+--------------------+-------------------------------
 llava:7b      | llava:7b      | 4733363377 | 8dd30f6b0cb19f555f2c7a7ebda861449ea2cc76bf1f44e262931f45fc81d081 | llama  | gguf   | ["llama", "clip"] |              | 7B             | Q4_0               | 2024-06-17 21:01:26.225392+00
 llama3:latest | llama3:latest | 4661224676 | 365c0bd3c000a25d28ddbf732fe1c6add414de7275464c4e4d1c3b5fcb5d8ad1 | llama  | gguf   | ["llama"]         |              | 8.0B           | Q4_0               | 2024-06-12 21:28:38.49735+00
(2 rows)
```

### Tokenize

#### OpenAI tokenize

To encode content and count the number of tokens returned:

* Encode content into an array of tokens.

    ```sql
    SELECT openai_tokenize
    ( 'text-embedding-ada-002'
    , 'Timescale is Postgres made Powerful'
    );
    ```
  The data returned looks like:
    ```text
                openai_tokenize             
    ----------------------------------------
     {19422,2296,374,3962,18297,1903,75458}
    (1 row)
    ```

* Count the number of tokens generated:

    ```sql
    SELECT array_length
    ( openai_tokenize
      ( 'text-embedding-ada-002'
      , 'Timescale is Postgres made Powerful'
      )
    , 1
    );
    ```
  The data returned looks like:
    ```text
     array_length 
    --------------
                7
    (1 row)
    ```

### Detokenize

#### OpenAI detokenize

Turn tokenized content into natural language:

```sql
SELECT openai_detokenize('text-embedding-ada-002', array[1820,25977,46840,23874,389,264,2579,58466]);
```
The data returned looks like:

```text
             openai_detokenize              
--------------------------------------------
 the purple elephant sits on a red mushroom
(1 row)
```

### Embed

#### OpenAI embed

Generate [embeddings](https://platform.openai.com/docs/guides/embeddings) using a specified model.

- Request an embedding using a specific model.

    ```sql
    SELECT openai_embed
    ( 'text-embedding-ada-002'
    , 'the purple elephant sits on a red mushroom'
    );
    ```

  The data returned looks like:

    ```text
                          openai_embed                      
    --------------------------------------------------------
     [0.005978798,-0.020522336,...-0.0022857306,-0.023699166]
    (1 row)
    ```

- Specify the number of dimensions you want in the returned embedding:

    ```sql
    SELECT openai_embed
    ( 'text-embedding-ada-002'
    , 'the purple elephant sits on a red mushroom'
    , _dimensions=>768
    );
    ```
  This only works for certain models.

- Pass a user identifier.

    ```sql
    SELECT openai_embed
    ( 'text-embedding-ada-002'
    , 'the purple elephant sits on a red mushroom'
    , _user=>'bac1aaf7-4460-42d3-bba5-2957b057f4a5'
    );
    ```

- Pass an array of text inputs.

    ```sql
    SELECT openai_embed
    ( 'text-embedding-ada-002'
    , array['Timescale is Postgres made Powerful', 'the purple elephant sits on a red mushroom']
    );
    ```

- Provide tokenized input.

    ```sql
    select openai_embed
    ( 'text-embedding-ada-002'
    , array[1820,25977,46840,23874,389,264,2579,58466]
    );
    ```

#### Ollama embed

Generate [embeddings](https://github.com/ollama/ollama/blob/main/docs/api.md#generate-embeddings) using a specified model.

```sql
select ollama_embed
( 'llama3'
, 'the purple elephant sits on a red mushroom'
);
```

The data returned looks like:

```text
                      ollama_embed                      
--------------------------------------------------------
    [0.65253496,0.63268006,... 1.5451192,-2.6915514]
(1 row)

```

### Chat complete

#### OpenAi chat complete

Generate text or complete a chat:

* Have an LLM generate text from a prompt:

    ```sql
    -- the following two metacommands cause the raw query results to be printed
    -- without any decoration
    \pset tuples_only on
    \pset format unaligned
    
    SELECT jsonb_pretty
    (
      openai_chat_complete
      ( 'gpt-4o'
      , jsonb_build_array
        ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
        , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
        )
      )
    );
    ```
  The data returned looks like:
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

- Return the content as text from a specific message in the choices array.

  `openai_chat_complete` returns a [jsonb object](https://www.depesz.com/2014/03/25/waiting-for-9-4-introduce-jsonb-a-structured-format-for-storing-json/) containing the
  response from the API. You can use jsonb operators and functions to manipulate [the object returned](https://platform.openai.com/docs/api-reference/chat/object). For example, the
  following query returns the content as text from the first message in the choices array.

    ```sql
    -- the following two metacommands cause the raw query results to be printed
    -- without any decoration
    \pset tuples_only on
    \pset format unaligned
    
    select openai_chat_complete
    ( 'gpt-4o'
    , jsonb_build_array
      ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
      , jsonb_build_object('role', 'user', 'content', 'what is the typical weather like in Alabama in June')
      )
    )->'choices'->0->'message'->>'content'
    ;
    ```
  The data returned looks like:

    ```text
    In June, Alabama generally experiences warm to hot weather as it transitions into summer. Typical conditions include:
    
    1. **Temperatures**: Daytime highs usually range from the mid-80s to low 90s Fahrenheit (around 29-34°C). Nighttime lows typically range from the mid-60s to low 70s Fahrenheit (around 18-23°C).
    
    2. **Humidity**: June tends to be quite humid, which can make the temperatures feel even warmer. High humidity levels are characteristic of Alabama summers.
    
    3. **Precipitation**: June is part of the wetter season in Alabama, with regular afternoon thunderstorms being common. Rainfall can vary, but you can expect an average of about 4 to 5 inches (around 100-125 mm) of rain for the month.
    
    4. **Sunshine**: There are usually plenty of sunny days, although the frequent thunderstorms can lead to overcast skies at times.
    
    Overall, if you're planning to visit Alabama in June, be prepared for hot and humid conditions, and keep an umbrella or rain jacket handy for those afternoon storms.
    ```

#### Ollama chat complete

[Generate text or complete a chat](https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-completion):

You can specify custom parameters to the LLM by providing the optional `_options` argument.

```sql
-- the following two metacommands cause the raw query results to be printed
-- without any decoration
\pset tuples_only on
\pset format unaligned

select jsonb_pretty(
  ollama_chat_complete
  ( 'llama3'
  , jsonb_build_array
    ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
    , jsonb_build_object('role', 'user', 'content', 'Give a short description of what a large language model is')
    )
  , _options=> jsonb_build_object
    ( 'seed', 42
    , 'temperature', 0.6
    )
  )
);
```
The data returned looks like:

```json
{
  "done": true,
  "model": "llama3",
  "message": {
    "role": "assistant",
    "content": "A large language model (LLM) is a type of artificial intelligence designed to process and generate human-like language. It's trained on massive amounts of text data, such as books, articles, and online conversations, which allows it to learn patterns, relationships, and nuances of language.\n\nAn LLM can perform various tasks, including:\n\n1. Natural Language Processing (NLP): understanding and generating human language.\n2. Text generation: creating original text based on input prompts or topics.\n3. Question answering: providing accurate answers to questions posed in natural language.\n4. Sentiment analysis: determining the emotional tone or sentiment behind a piece of text.\n\nLarge language models are typically trained using deep learning algorithms, such as transformer-based architectures (like BERT, RoBERTa, and XLNet), which enable them to learn from vast amounts of data and generate coherent, context-specific responses.\n\nThese models have numerous applications in areas like:\n\n1. Virtual assistants: providing helpful information and answering user queries.\n2. Language translation: facilitating communication between people speaking different languages.\n3. Content creation: generating text for articles, blog posts, or even entire books.\n4. Chatbots: enabling conversational interfaces that can engage with users.\n\nIn summary, a large language model is a powerful AI tool capable of processing and generating human-like language, with applications in various industries and aspects of our lives!"
  },
  "created_at": "2024-06-18T19:57:09.011458Z",
  "eval_count": 278,
  "done_reason": "stop",
  "eval_duration": 8380764000,
  "load_duration": 4187544583,
  "total_duration": 12715492417,
  "prompt_eval_count": 31,
  "prompt_eval_duration": 142132000
}
```

You can use [jsonb operators and functions](https://www.postgresql.org/docs/current/functions-json.html#FUNCTIONS-JSON-PROCESSING) 
to manipulate the jsonb object returned from `ollama_chat_complete`.

```sql
-- the following two metacommands cause the raw query results to be printed
-- without any decoration
\pset tuples_only on
\pset format unaligned

select ollama_chat_complete
( 'llama3'
, jsonb_build_array
  ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
  , jsonb_build_object('role', 'user', 'content', 'Give a short description of what a large language model is')
  )
, _options=> jsonb_build_object
  ( 'seed', 42
  , 'temperature', 0.6
  )
)->'message'->>'content';
```

The data returned looks like:

```text
A large language model (LLM) is a type of artificial intelligence designed to process and generate human-like language. It's trained on massive amounts of text data, such as books, articles, and online conversations, which allows it to learn patterns, relationships, and nuances of language.

An LLM can perform various tasks, including:

1. Natural Language Processing (NLP): understanding and generating human language.
2. Text generation: creating original text based on input prompts or topics.
3. Question answering: providing accurate answers to questions posed in natural language.
4. Sentiment analysis: determining the emotional tone or sentiment behind a piece of text.

Large language models are typically trained using deep learning algorithms, such as transformer-based architectures (like BERT, RoBERTa, and XLNet), which enable them to learn from vast amounts of data and generate coherent, context-specific responses.

These models have numerous applications in areas like:

1. Virtual assistants: providing helpful information and answering user queries.
2. Language translation: facilitating communication between people speaking different languages.
3. Content creation: generating text for articles, blog posts, or even entire books.
4. Chatbots: enabling conversational interfaces that can engage with users.

In summary, a large language model is a powerful AI tool capable of processing and generating human-like language, with applications in various industries and aspects of our lives!
```

### Generate

#### Ollama generate

[Generate a response for the prompt provided](https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-completion)

```sql
-- the following two metacommands cause the raw query results to be printed
-- without any decoration
\pset tuples_only on
\pset format unaligned

select ollama_generate
( 'llava:7b'
, 'Please describe this image.'
, _images=> array[pg_read_binary_file('/pgai/tests/postgresql-vs-pinecone.jpg')]
, _system=>'you are a helpful assistant'
, _options=> jsonb_build_object
  ( 'seed', 42
  , 'temperature', 0.9
  )
)->>'response'
;
```

The data returned looks like:

```text
 This is a digital image featuring two anthropomorphic characters that appear to be stylized animals. On the left, there's a character that looks like an elephant with boxing gloves on, ready for a fight. The elephant has large ears and eyes, and it's standing upright.

On the right, there's a character that resembles a pine cone. This character is also anthropomorphic, wearing shorts, boots, and a bandana. It holds what looks like a pine cone in each hand.

The background of the image suggests an indoor setting with a wooden floor, a stage with lights, and spectators in the stands. The overall atmosphere of the scene is competitive and energetic. 
```

### Moderate

Check if content is classified as potentially harmful:

#### OpenAI Moderate

```sql
-- the following two metacommands cause the raw query results to be printed
-- without any decoration
\pset tuples_only on
\pset format unaligned

select jsonb_pretty
(
  openai_moderate
  ( 'text-moderation-stable'
  , 'I want to kill them.'
  )
);
```
The data returned looks like:

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

### List running models

#### Ollama list running models

You can [list the models currently running in Ollama](https://github.com/ollama/ollama/blob/main/docs/api.md#list-running-models) with:

```sql
select *
from ollama_ps()
;
```

The data returned looks like:

```text
   name   |  model   |    size    |                              digest                              | parent_model | format | family |     families      | parameter_size | quantization_level |          expires_at           | size_vram  
----------+----------+------------+------------------------------------------------------------------+--------------+--------+--------+-------------------+----------------+--------------------+-------------------------------+------------
 llava:7b | llava:7b | 5758857216 | 8dd30f6b0cb19f555f2c7a7ebda861449ea2cc76bf1f44e262931f45fc81d081 |              | gguf   | llama  | ["llama", "clip"] | 7B             | Q4_0               | 2024-06-18 20:07:30.508198+00 | 5758857216
(1 row)
```

## Advanced examples

For more advanced usage, the [Advanced examples](docs/advanced.md) use pgai to embed, moderate,
and summarize a git commit history.

Combine with triggers to [moderate comments](docs/moderate.md) or
[populate embeddings](docs/delayed_embed.md) in the background.

## Provider-specific Setup

### OpenAI

Most pgai functions require an [OpenAI API key](https://platform.openai.com/docs/quickstart/step-2-set-up-your-api-key).

- [Handle API keys using pgai from psql](#handle-api-keys-using-pgai-from-psql)
- [Handle API keys using pgai from python](#handle-api-keys-using-pgai-from-python)

#### Handle API keys using pgai from psql

The api key is an [optional parameter to pgai functions](https://www.postgresql.org/docs/current/sql-syntax-calling-funcs.html).
You can either:

* [Run AI queries by passing your API key implicitly as a session parameter](#run-ai-queries-by-passing-your-api-key-implicitly-as-a-session-parameter)
* [Run AI queries by passing your API key explicitly as a function argument](#run-ai-queries-by-passing-your-api-key-explicitly-as-a-function-argument)

##### Run AI queries by passing your API key implicitly as a session parameter

To use a [session level parameter when connecting to your database with psql](https://www.postgresql.org/docs/current/config-setting.html#CONFIG-SETTING-SHELL)
to run your AI queries:

1. Set your OpenAI key as an environment variable in your shell:
    ```bash
    export OPENAI_API_KEY="this-is-my-super-secret-api-key-dont-tell"
    ```
1. Use the session level parameter when you connect to your database:

    ```bash
    PGOPTIONS="-c ai.openai_api_key=$OPENAI_API_KEY" psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>"
    ```

1. Run your AI query:

    `ai.openai_api_key` is set for the duration of your psql session, you do not need to specify it for pgai functions.

    ```sql
    SELECT * 
    FROM openai_list_models()
    ORDER BY created DESC
    ;
    ```

##### Run AI queries by passing your API key explicitly as a function argument

1. Set your OpenAI key as an environment variable in your shell:
    ```bash
    export OPENAI_API_KEY="this-is-my-super-secret-api-key-dont-tell"
    ```

2. Connect to your database and set your api key as a [psql variable](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-VARIABLES).

      ```bash
      psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>" -v openai_api_key=$OPENAI_API_KEY
      ```
      Your API key is now available as a psql variable named `openai_api_key` in your psql session.

      You can also log into the database, then set `openai_api_key` using the `\getenv` [metacommand](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-META-COMMAND-GETENV):   

      ```sql
       \getenv openai_api_key OPENAI_API_KEY
      ```

4. Pass your API key to your parameterized query:
    ```sql
    SELECT * 
    FROM openai_list_models(_api_key=>$1)
    ORDER BY created DESC
    \bind :openai_api_key
    \g
    ```

    Use [\bind](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-META-COMMAND-BIND) to pass the value of `openai_api_key` to the parameterized query.

    The `\bind` metacommand is available in psql version 16+.

#### Handle API keys using pgai from python

1. In your Python environment, include the dotenv and postgres driver packages:

    ```bash
    pip install python-dotenv
    pip install psycopg2-binary
    ```

1. Set your OpenAI key in a .env file or as an environment variable:
    ```bash
    OPENAI_API_KEY="this-is-my-super-secret-api-key-dont-tell"
    DB_URL="your connection string"
    ```

1. Pass your API key as a parameter to your queries:

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
            cur.execute("SELECT * FROM openai_list_models(_api_key=>%s) ORDER BY created DESC", (OPENAI_API_KEY,))
            records = cur.fetchall()
    ```

    Do not use string manipulation to embed the key as a literal in the SQL query.

### Ollama

You will need to have Ollama running somewhere that is network-accessible to your database.
The Ollama functions in pgai take an optional `_host` parameter to specify where Ollama is.

If you are running Postgres in a docker container, and Ollama is running on the host machine,
use `http://host.docker.internal:11434` for the `_host`.

You can provide an argument explicitly like this:

```sql
select ollama_generate
( 'llama3'
, 'what is the typical weather like in Alabama in June'
, _host=>'http://host.docker.internal:11434' -- tells pgai that Ollama is running on the host when pgai is in a docker container
)
```

Alternately, you can set the `ai.ollama_host` config parameter.

To do this at a session level, run:

```sql
select set_config('ai.ollama_host', 'http://host.docker.internal:11434', false);
```

Or to do it system-wide, you can [add it to the postgres.conf file](https://www.postgresql.org/docs/current/config-setting.html#CONFIG-SETTING-CONFIGURATION-FILE).

If the `_host` parameter is not specified explicitly and the `ai.ollama_host` config
setting is missing, the Ollama functions will default to `http://localhost:11434`. 
This will generate a warning in the log file.

## Get involved

pgai is still at an early stage. Now is a great time to help shape the direction of this project; 
we are currently deciding priorities. Have a look at the [list of features](https://github.com/timescale/pgai/issues) we're thinking of working on. 
Feel free to comment, expand the list, or hop on the Discussions forum.

To get started, take a look at [how to contribute](./CONTRIBUTING.md) 
and [how to set up a dev/test environment](./DEVELOPMENT.md).

## About Timescale

Timescale is a PostgreSQL database company. To learn more visit the [timescale.com](https://www.timescale.com).

Timescale Cloud is a high-performance, developer focused, cloud platform that provides PostgreSQL services
for the most demanding AI, time-series, analytics, and event workloads. Timescale Cloud is ideal for production applications and provides high availability, streaming backups, upgrades over time, roles and permissions, and great security.
