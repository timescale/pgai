# Use pgai with Cohere

This page shows you how to:

- [Configure pgai for Cohere](#configure-pgai-for-cohere)
- [Add AI functionality to your database](#usage)

## Configure pgai for Cohere

Cohere functions in pgai require an [Cohere API key](https://docs.cohere.com/docs/rate-limits).

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

1. Set your Cohere key as an environment variable in your shell:
    ```bash
    export COHERE_API_KEY="this-is-my-super-secret-api-key-dont-tell"
    ```
1. Use the session level parameter when you connect to your database:

    ```bash
    PGOPTIONS="-c ai.cohere_api_key=$COHERE_API_KEY" psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>"
    ```

1. Run your AI query:

   `ai.cohere_api_key` is set for the duration of your psql session, you do not need to specify it for pgai functions.

    ```sql
    SELECT ai.cohere_chat_complete
    ( 'command-r-plus'
    , 'How much wood would a woodchuck chuck if a woodchuck could chuck wood?'
    , _seed=>42
    )->>'text'
    ;
    ```

#### Run AI queries by passing your API key explicitly as a function argument

1. Set your Cohere key as an environment variable in your shell:
    ```bash
    export COHERE_API_KEY="this-is-my-super-secret-api-key-dont-tell"
    ```

2. Connect to your database and set your api key as a [psql variable](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-VARIABLES):

      ```bash
      psql -d "postgres://<username>:<password>@<host>:<port>/<database-name>" -v cohere_api_key=$COHERE_API_KEY
      ```
   Your API key is now available as a psql variable named `cohere_api_key` in your psql session.

   You can also log into the database, then set `cohere_api_key` using the `\getenv` [metacommand](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-META-COMMAND-GETENV):

      ```sql
       \getenv cohere_api_key COHERE_API_KEY
      ```

4. Pass your API key to your parameterized query:
    ```sql
    SELECT ai.cohere_chat_complete
    ( 'command-r-plus'
    , 'How much wood would a woodchuck chuck if a woodchuck could chuck wood?'
    , _api_key=>$1
    , _seed=>42
    )->>'text'
    \bind :cohere_api_key
    \g
    ```

   Use [\bind](https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-META-COMMAND-BIND) to pass the value of `cohere_api_key` to the parameterized query.

   The `\bind` metacommand is available in psql version 16+.

### Handle API keys using pgai from python

1. In your Python environment, include the dotenv and postgres driver packages:

    ```bash
    pip install python-dotenv
    pip install psycopg2-binary
    ```

2. Set your Cohere API key in a .env file or as an environment variable:
    ```bash
    COHERE_API_KEY="this-is-my-super-secret-api-key-dont-tell"
    DB_URL="your connection string"
    ```

3. Pass your API key as a parameter to your queries:

    ```python
    import os
    from dotenv import load_dotenv
         
    load_dotenv()
        
    COHERE_API_KEY = os.environ["COHERE_API_KEY"]
    DB_URL = os.environ["DB_URL"]
        
    import psycopg2
        
    with psycopg2.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            # pass the API key as a parameter to the query. don't use string manipulations
            cur.execute("""
                SELECT ai.cohere_chat_complete
                ( 'command-r-plus'
                , 'How much wood would a woodchuck chuck if a woodchuck could chuck wood?'
                , _api_key=>%s
                , _seed=>42
                )->>'text'
            """, (COHERE_API_KEY, ))
            records = cur.fetchall()
    ```

   Do not use string manipulation to embed the key as a literal in the SQL query.

## Usage

This section shows you how to use AI directly from your database using SQL.

- [cohere_list_models](#cohere_list_models)
- [cohere_tokenize](#cohere_tokenize)
- [cohere_detokenize](#cohere_detokenize)
- [cohere_embed](#cohere_embed)
- [cohere_classify](#cohere_classify)
- [cohere_classify_simple](#cohere_classify_simple)
- [cohere_rerank](#cohere_rerank)
- [cohere_rerank_simple](#cohere_rerank_simple)
- [cohere_chat_complete](#cohere_chat_complete)

### cohere_list_models

* List the models supported by the Cohere platform.
  
  ```sql
  select *
  from ai.cohere_list_models()
  ;
  ```
  
  Results:
  
  ```text
               name              |         endpoints         | finetuned | context_length |                                       tokenizer_url                                        | default_endpoints 
  -------------------------------+---------------------------+-----------+----------------+--------------------------------------------------------------------------------------------+-------------------
   embed-english-light-v2.0      | {embed,classify}          | f         |            512 |                                                                                            | {}
   embed-english-v2.0            | {embed,classify}          | f         |            512 |                                                                                            | {}
   command-r                     | {generate,chat,summarize} | f         |         128000 | https://storage.googleapis.com/cohere-public/tokenizers/command-r.json                     | {}
   embed-multilingual-light-v3.0 | {embed,classify}          | f         |            512 | https://storage.googleapis.com/cohere-public/tokenizers/embed-multilingual-light-v3.0.json | {}
   command-nightly               | {generate,chat,summarize} | f         |         128000 | https://storage.googleapis.com/cohere-public/tokenizers/command-nightly.json               | {}
   command-r-plus                | {generate,chat,summarize} | f         |         128000 | https://storage.googleapis.com/cohere-public/tokenizers/command-r-plus.json                | {chat}
   embed-multilingual-v3.0       | {embed,classify}          | f         |            512 | https://storage.googleapis.com/cohere-public/tokenizers/embed-multilingual-v3.0.json       | {}
   embed-multilingual-v2.0       | {embed,classify}          | f         |            256 | https://storage.googleapis.com/cohere-public/tokenizers/embed-multilingual-v2.0.json       | {}
   c4ai-aya-23                   | {generate,chat}           | f         |           8192 | https://storage.googleapis.com/cohere-public/tokenizers/c4ai-aya-23.json                   | {}
   command-light-nightly         | {generate,summarize,chat} | f         |           4096 | https://storage.googleapis.com/cohere-public/tokenizers/command-light-nightly.json         | {}
   rerank-multilingual-v2.0      | {rerank}                  | f         |            512 | https://storage.googleapis.com/cohere-public/tokenizers/rerank-multilingual-v2.0.json      | {}
   embed-english-v3.0            | {embed,classify}          | f         |            512 | https://storage.googleapis.com/cohere-public/tokenizers/embed-english-v3.0.json            | {}
   command                       | {generate,summarize,chat} | f         |           4096 | https://storage.googleapis.com/cohere-public/tokenizers/command.json                       | {generate}
   rerank-multilingual-v3.0      | {rerank}                  | f         |           4096 | https://storage.googleapis.com/cohere-public/tokenizers/rerank-multilingual-v3.0.json      | {}
   rerank-english-v2.0           | {rerank}                  | f         |            512 | https://storage.googleapis.com/cohere-public/tokenizers/rerank-english-v2.0.json           | {}
   command-light                 | {generate,summarize,chat} | f         |           4096 | https://storage.googleapis.com/cohere-public/tokenizers/command-light.json                 | {}
   rerank-english-v3.0           | {rerank}                  | f         |           4096 | https://storage.googleapis.com/cohere-public/tokenizers/rerank-english-v3.0.json           | {}
   embed-english-light-v3.0      | {embed,classify}          | f         |            512 | https://storage.googleapis.com/cohere-public/tokenizers/embed-english-light-v3.0.json      | {}
  (18 rows)
  ```

* List the models on the Cohere platform that support a particular endpoint.
  
  ```sql
  select *
  from ai.cohere_list_models(_endpoint=>'embed')
  ;
  ```
  
  Results
  
  ```text
               name              |    endpoints     | finetuned | context_length |                                       tokenizer_url                                        | default_endpoints 
  -------------------------------+------------------+-----------+----------------+--------------------------------------------------------------------------------------------+-------------------
   embed-english-light-v2.0      | {embed,classify} | f         |            512 |                                                                                            | {}
   embed-english-v2.0            | {embed,classify} | f         |            512 |                                                                                            | {}
   embed-multilingual-light-v3.0 | {embed,classify} | f         |            512 | https://storage.googleapis.com/cohere-public/tokenizers/embed-multilingual-light-v3.0.json | {}
   embed-multilingual-v3.0       | {embed,classify} | f         |            512 | https://storage.googleapis.com/cohere-public/tokenizers/embed-multilingual-v3.0.json       | {}
   embed-multilingual-v2.0       | {embed,classify} | f         |            256 | https://storage.googleapis.com/cohere-public/tokenizers/embed-multilingual-v2.0.json       | {}
   embed-english-v3.0            | {embed,classify} | f         |            512 | https://storage.googleapis.com/cohere-public/tokenizers/embed-english-v3.0.json            | {}
   embed-english-light-v3.0      | {embed,classify} | f         |            512 | https://storage.googleapis.com/cohere-public/tokenizers/embed-english-light-v3.0.json      | {}
  (7 rows)
  ```

* List the default model for a given endpoint.
  
  ```sql
  select * 
  from ai.cohere_list_models(_endpoint=>'generate', _default_only=>true);
  ```
  
  Results
  
  ```text
    name   |         endpoints         | finetuned | context_length |                            tokenizer_url                             | default_endpoints 
  ---------+---------------------------+-----------+----------------+----------------------------------------------------------------------+-------------------
   command | {generate,summarize,chat} | f         |           4096 | https://storage.googleapis.com/cohere-public/tokenizers/command.json | {generate}
  (1 row)
  ```

### cohere_tokenize

Tokenize text content.

```sql
select ai.cohere_tokenize
( 'command'
, 'One of the best programming skills you can have is knowing when to walk away for awhile.'
);
```

Results:

```text
                                      cohere_tokenize                                       
--------------------------------------------------------------------------------------------
 {5256,1707,1682,2383,9461,4696,1739,1863,1871,1740,9397,2112,1705,4066,3465,1742,38700,21}
(1 row)
```

### cohere_detokenize

Reverse the tokenize process.

```sql
select ai.cohere_detokenize
( 'command'
, array[14485,38374,2630,2060,2252,5164,4905,21,2744,2628,1675,3094,23407,21]
);
```

Results:

```text
                              cohere_detokenize                               
------------------------------------------------------------------------------
 Good programmers don't just write programs. They build a working vocabulary.
(1 row)
```

### cohere_embed

Embed content.

```sql
select ai.cohere_embed
( 'embed-english-light-v3.0'
, 'if a woodchuck could chuck wood, a woodchuck would chuck as much wood as he could'
, _input_type=>'search_document'
);
```

Results:

```text
                     cohere_embed                      
-------------------------------------------------------
 [-0.066833496,-0.052337646,...0.014167786,0.02053833]
(1 row)
```

### cohere_classify

Classify inputs, assigning labels.

```sql
with examples(example, label) as
(
    values
      ('cat', 'animal')
    , ('dog', 'animal')
    , ('car', 'machine')
    , ('truck', 'machine')
    , ('apple', 'food')
    , ('broccoli', 'food')
)
select *
from jsonb_to_recordset
(
    ai.cohere_classify
    ( 'embed-english-light-v3.0'
    , array['bird', 'airplane', 'corn'] --inputs we want to classify
    , _examples=>(select jsonb_agg(jsonb_build_object('text', examples.example, 'label', examples.label)) from examples)
    )->'classifications'
) x(input text, prediction text, confidence float8)
;
```

Results:

```text
  input   | prediction | confidence 
----------+------------+------------
 bird     | animal     |  0.3708435
 airplane | machine    |   0.343932
 corn     | food       | 0.37896726
(3 rows)
```

### cohere_classify_simple

A simpler interface to classification.

```sql
with examples(example, label) as
(
    values
      ('cat', 'animal')
    , ('dog', 'animal')
    , ('car', 'machine')
    , ('truck', 'machine')
    , ('apple', 'food')
    , ('broccoli', 'food')
)
select *
from ai.cohere_classify_simple
( 'embed-english-light-v3.0'
, array['bird', 'airplane', 'corn']
, _examples=>(select jsonb_agg(jsonb_build_object('text', examples.example, 'label', examples.label)) from examples)
) x
;
```

Results:

```text
  input   | prediction | confidence 
----------+------------+------------
 bird     | animal     |  0.3708435
 airplane | machine    |   0.343932
 corn     | food       | 0.37896726
(3 rows)
```

### cohere_rerank

Rank documents according to semantic similarity to a query prompt.

```sql
select
  x."index"
, x.document->>'text' as "text"
, x.relevance_score
from jsonb_to_recordset
(
    ai.cohere_rerank
    ( 'rerank-english-v3.0'
    , 'How long does it take for two programmers to work on something?'
    , jsonb_build_array
      ( $$Good programmers don't just write programs. They build a working vocabulary.$$
      , 'One of the best programming skills you can have is knowing when to walk away for awhile.'
      , 'What one programmer can do in one month, two programmers can do in two months.'
      , 'how much wood would a woodchuck chuck if a woodchuck could chuck wood?'
      )
    , _return_documents=>true
    )->'results'
) x("index" int, "document" jsonb, relevance_score float8)
order by relevance_score desc
;
```

Results:

```text
 index |                                           text                                           | relevance_score 
-------+------------------------------------------------------------------------------------------+-----------------
     2 | What one programmer can do in one month, two programmers can do in two months.           |       0.8003801
     0 | Good programmers don't just write programs. They build a working vocabulary.             |    0.0011559008
     1 | One of the best programming skills you can have is knowing when to walk away for awhile. |    0.0006932423
     3 | how much wood would a woodchuck chuck if a woodchuck could chuck wood?                   |    2.637042e-07
(4 rows)
```

### cohere_rerank_simple

A simpler interface to rerank.

```sql
select *
from ai.cohere_rerank_simple
( 'rerank-english-v3.0'
, 'How long does it take for two programmers to work on something?'
, jsonb_build_array
  ( $$Good programmers don't just write programs. They build a working vocabulary.$$
  , 'One of the best programming skills you can have is knowing when to walk away for awhile.'
  , 'What one programmer can do in one month, two programmers can do in two months.'
  , 'how much wood would a woodchuck chuck if a woodchuck could chuck wood?'
  )
) x
order by relevance_score desc
;
```

Results:

```text
 index |                                               document                                               | relevance_score 
-------+------------------------------------------------------------------------------------------------------+-----------------
     2 | {"text": "What one programmer can do in one month, two programmers can do in two months."}           |       0.8003801
     0 | {"text": "Good programmers don't just write programs. They build a working vocabulary."}             |    0.0011559008
     1 | {"text": "One of the best programming skills you can have is knowing when to walk away for awhile."} |    0.0006932423
     3 | {"text": "how much wood would a woodchuck chuck if a woodchuck could chuck wood?"}                   |    2.637042e-07
(4 rows)
```

### cohere_chat_complete

Complete chat prompts

```sql
select ai.cohere_chat_complete
( 'command-r-plus'
, 'How much wood would a woodchuck chuck if a woodchuck could chuck wood?'
, _seed=>42
)->>'text'
;
```

Results:

```text
According to a tongue-twister poem often attributed to Robert Hobart Davis and Richard Wayne Peck, a woodchuck (also known as a groundhog) would chuck, or throw, “as much wood as a woodchuck would, if a woodchuck could chuck wood.” 

In a more serious biological context, woodchucks are known to be capable of causing significant damage to wood-based structures and landscapes due to their burrowing and chewing habits. They can chew through small trees and branches, although the exact amount of wood they could chuck or chew through would depend on various factors such as the size and age of the woodchuck, the type and condition of the wood, and the woodchuck's motivation and determination.
```

