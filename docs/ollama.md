# Use pgai with Ollama

This page shows you how to:

- [Configure pgai for Ollama](#configure-pgai-for-ollama)
- [Add AI functionality to your database](#usage)

## Configure pgai for Ollama

To use pgai with Ollama, Ollama must be running and network-accessible to your database.

To specify the Ollama network address, Ollama functions in pgai use the `host` parameter. Alternatively, the `ai.ollama_host` config setting can used.
If you do not pass a `host` argument, and the `ai.ollama_host` config setting is missing, pgai defaults to 
`http://localhost:11434`, and a warning is appended to the log file.

You set the network for your Ollama configuration either:

* Explicitly with the `host` parameter:

  ```sql
  select ai.ollama_generate
  ( 'llama3'
  , 'what is the typical weather like in Alabama in June'
  , host=>'http://host.for.ollama:port' -- tells pgai that Ollama is running on the host when pgai is in a docker container
  )
  ```

* Using the `ai.ollama_host` config parameter:

  * At a session level:

    ```sql
    select set_config('ai.ollama_host', 'http://host.for.ollama:port', false);
    ```

  * System-wide, [add it to the postgres.conf file](https://www.postgresql.org/docs/current/config-setting.html#CONFIG-SETTING-CONFIGURATION-FILE)


When Ollama is running on the same host machine as the [Docker container](../README.md#use-a-pre-built-docker-container) 
running pgai, the ollama host address is `http://host.docker.internal:11434`.

## Usage

This section shows you how to use AI directly from your database using SQL.

- [List_models](#list-models): list the models supported by Ollama functions in pgai.
- [Embed](#embed): generate embeddings using a specified model.
- [Chat_complete](#chat-complete): generate text or complete a chat.
- [Generate](#generate): generate a response to a prompt
- [List running models](#list-running-models): list the models currently running

### List models

List the models supported by your AI provider in pgai:

```sql
SELECT * 
FROM ai.ollama_list_models()
ORDER BY size DESC
;
```
The data returned looks something like the following. However this depends on the models pulled in 
your Ollama instance:

```text
     name      |     model     |    size    |                              digest                              | family | format |     families      | parent_model | parameter_size | quantization_level |          modified_at          
---------------+---------------+------------+------------------------------------------------------------------+--------+--------+-------------------+--------------+----------------+--------------------+-------------------------------
 llava:7b      | llava:7b      | 4733363377 | 8dd30f6b0cb19f555f2c7a7ebda861449ea2cc76bf1f44e262931f45fc81d081 | llama  | gguf   | ["llama", "clip"] |              | 7B             | Q4_0               | 2024-06-17 21:01:26.225392+00
 llama3:latest | llama3:latest | 4661224676 | 365c0bd3c000a25d28ddbf732fe1c6add414de7275464c4e4d1c3b5fcb5d8ad1 | llama  | gguf   | ["llama"]         |              | 8.0B           | Q4_0               | 2024-06-12 21:28:38.49735+00
(2 rows)
```

### Embed

Generate [embeddings](https://github.com/ollama/ollama/blob/main/docs/api.md#generate-embeddings) using a specified model:

```sql
select ai.ollama_embed
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

[Generate text or complete a chat](https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-completion).
You specify custom parameters to the LLM using optional `_options` argument:

```sql
-- the following two metacommands cause the raw query results to be printed
-- without any decoration
\pset tuples_only on
\pset format unaligned

select jsonb_pretty(
  ai.ollama_chat_complete
  ( 'llama3'
  , jsonb_build_array
    ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
    , jsonb_build_object('role', 'user', 'content', 'Give a short description of what a large language model is')
    )
  , chat_options=> jsonb_build_object
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
to manipulate the jsonb object returned from `ollama_chat_complete`:

```sql
-- the following two metacommands cause the raw query results to be printed
-- without any decoration
\pset tuples_only on
\pset format unaligned

select ai.ollama_chat_complete
( 'llama3'
, jsonb_build_array
  ( jsonb_build_object('role', 'system', 'content', 'you are a helpful assistant')
  , jsonb_build_object('role', 'user', 'content', 'Give a short description of what a large language model is')
  )
, chat_options=> jsonb_build_object
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

[Generate a response for the prompt provided](https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-completion):

```sql
-- the following two metacommands cause the raw query results to be printed
-- without any decoration
\pset tuples_only on
\pset format unaligned

select ai.ollama_generate
( 'llava:7b'
, 'Please describe this image.'
, images=> array[pg_read_binary_file('/pgai/tests/postgresql-vs-pinecone.jpg')]
, system_prompt=>'you are a helpful assistant'
, embedding_options=> jsonb_build_object
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

### List running models

You [list the models currently running in Ollama](https://github.com/ollama/ollama/blob/main/docs/api.md#list-running-models) with:

```sql
select *
from ai.ollama_ps()
;
```

The data returned looks like:

```text
   name   |  model   |    size    |                              digest                              | parent_model | format | family |     families      | parameter_size | quantization_level |          expires_at           | size_vram  
----------+----------+------------+------------------------------------------------------------------+--------------+--------+--------+-------------------+----------------+--------------------+-------------------------------+------------
 llava:7b | llava:7b | 5758857216 | 8dd30f6b0cb19f555f2c7a7ebda861449ea2cc76bf1f44e262931f45fc81d081 |              | gguf   | llama  | ["llama", "clip"] | 7B             | Q4_0               | 2024-06-18 20:07:30.508198+00 | 5758857216
(1 row)
```

