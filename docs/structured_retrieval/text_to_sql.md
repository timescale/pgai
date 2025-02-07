# Text to SQL

> **Disclaimer:** this feature is in early preview and not yet supported in any way for production.

## Overview

pgai Text to SQL makes it simple for developers to use data from PostgreSQL tables as context for LLM applications.

Whether you’re building a customer-facing chatbot or an internal tool, text to SQL can help with the following use cases:

* **Structured Retrieval** – Answer questions using only SQL tables. Example: “What is the median MRR of our customers?”  
* **Structured \+ Unstructured Retrieval** – Combine SQL with vector search for RAG apps. Example: “Show me accounts that mentioned *security* in sales calls (unstructured), but don’t have 2FA enabled (structured).”  
* **AI Agents** – Let AI agents retrieve structured and unstructured data. Example: A stock analyst agent that looks up time-series data (structured) and searches earnings reports (unstructured).

## API keys

Add your API key for your [LLM/embedding providers](#supported-providers):

1. Visit [Timescale Console](https://console.cloud.timescale.com/)  
2. Click on your service  
3. Click on AI in the top menu  
4. Click on Vectorizers in the left menu  
5. Click `Add an API key`  
6. For a list of all the providers we support and their API keys, see [Supported providers](#supported-providers).

## Fork your database

We recommend creating a fork of your database so you can safely experiment with text to SQL without impacting your production databases.

1. Visit Timescale Console  
2. Click on your service  
3. In the top right of your screen, click the three dot menu  
4. Click `Fork service`  
5. Email [support@timescale.com](mailto:support@timescale.com) your service ID and we will enable text to SQL functionality for your service

## Install or update the extension

Next, install the pgai extension. If you already have it installed, update it to the latest version. Note: you’ll need a specific version that has the text to SQL capabilities. 

```sql
/*
 * If it's your first time installing pgai
 */

select set_config('ai.enable_feature_flag_text_to_sql', 'true', false);
create extension if not exists ai cascade;

/*
 * If you already have pgai, update it
 */ 

select set_config('ai.enable_feature_flag_text_to_sql', 'true', false);
alter extension ai update;
```

## Create the semantic catalog

This function creates [vectorizers](https://github.com/timescale/pgai/blob/main/docs/vectorizer/overview.md) for the tables that pgai uses to store descriptions for tables, columns, and queries. These vectorizers will automatically generate embeddings for the descriptions and update them if you edit the descriptions.

For example:

```sql
-- OpenAI embeddings and OpenAI o1 completions
select ai.create_semantic_catalog(
  embedding=>ai.embedding_openai('text-embedding-3-small', 768)
, text_to_sql=>ai.text_to_sql_openai(model=>'o1')
);

-- OpenAI embeddings + Claude 3.5 Sonnet completions
select ai.create_semantic_catalog(
  embedding=>ai.embedding_openai('text-embedding-3-small', 768)
, text_to_sql=>ai.text_to_sql_anthropic(model=>'claude-3-5-sonnet-latest')
);

-- Voyage embeddings + Claude 3.5 Sonnet completions
select ai.create_semantic_catalog(
  embedding=>ai.embedding_voyageai('voyage-3-lite', 512)
, text_to_sql=>ai.text_to_sql_anthropic(model=>'claude-3-5-sonnet-latest')
);

-- Ollama embeddings + OpenAI o1 completions
select ai.create_semantic_catalog
( embedding=>ai.embedding_ollama
    ( 'nomic-embed-text'
    , 768
    , base_url=>'http://host.docker.internal:11434'
    )
, text_to_sql=>ai.text_to_sql_openai(model=>'o1')
);
```

The embedding parameter is the only required parameter. It defines how we will embed the descriptions of database objects and SQL examples. The semantic catalog supports the same embedding configurations supported by Vectorizer. So, you may use OpenAI, Ollama, VoyageAI, etc. The optional arguments will differ between the LLM provider, but you’ll need to specify a model and dimensions regardless.

The `text_to_sql` parameter establishes a default configuration for the `text_to_sql` function. The main purpose here is to define the model to be used for generating SQL. Optional arguments differ between the LLM providers. For a list of the providers we support, see [Supported providers](#supported-providers).

You can mix and match. For example, you can use Ollama for embeddings and Anthropic for SQL generation.

## Write descriptions

Write descriptions for tables, columns, and queries. pgai will give these descriptions to the LLM to help it create a more accurate query.

```sql
/*
 * Tables or views
 */

/* Upsert a description */
select ai.set_description('orders', 'The orders table stores details about individual orders....');

/* Delete a description */
select ai.delete_description('orders');

/*
 * Columns
 */

/* Upsert a description */
select ai.set_column_description('orders', 'dt', 'The timestamp at which the order was submitted. This column cannot be null.');

/* Delete a description */
select ai.delete_column_description('orders', 'dt');

/* Delete all column descriptions from a table */
select ai.delete_column_descriptions('orders');

/*
 * Functions
 */

/* Upsert a description */
select ai.set_function_description('myfunc'::regproc, 'This function returns all the orders with a "pending" status');

/* Delete a description */
select ai.delete_function_description('myfunc'::regproc);

/*
 * SQL queries
 */ 

/* Adding a description */
select ai.add_sql_example
( $$select date_trunc('day', o.dt) as day, avg(o.cost) as avg_cost from orders o where '2024-11-01'::date <= o.dt and o.dt < '2024-12-01'::date group by 1 order by 1$$
, 'This query calculates the daily average cost of orders in November. The orders table is filtered by the dt column to....'
);

/* Updating a description */
update ai.semantic_catalog_sql
set sql = 'new example'
where sql = 'old example';

/* Deleting a description */
delete from ai.semantic_catalog_sql
where sql = 'old example';
```

Wait for the descriptions to be embedded. You can monitor the queue with this query. These numbers should go to zero.

```sql
select
  ai.vectorizer_queue_pending(k.obj_vectorizer_id) as obj_pending,
  ai.vectorizer_queue_pending(k.sql_vectorizer_id) as sql_pending
from ai.semantic_catalog k
where k.catalog_name = 'default';
```

Want to generate your descriptions using LLMs so you don’t have to write them manually?

```sql
-- Generate a description for the `orders` table and print it
select ai.generate_description('orders');

-- Generate a description for the `orders` table, print it, and save it to the semantic catalog
-- If a description already exists, it will not overwrite
select ai.generate_description('orders', save => true);

-- Will save and overwrite the existing description
select ai.generate_description('orders', save => true, overwrite => true);

-- Generate and save descriptions for each column in the `orders` table
select ai.generate_column_descriptions('orders', save => true);

-- Generate and save a description for your `myfunc` function
select ai.generate_function_description('myfunc'::regproc, save => true);
```

## Use the `text_to_sql` function

Now you’re ready to use the `text_to_sql` function.

```sql
select ai.text_to_sql('show me the average order cost by day in November');

/*
             query             
-------------------------------
select
  date_trunc('day', o.dt) as day
, avg(o.cost) as avg_cost
from orders o
where '2024-11-01'::date <= o.dt
and o.dt < '2024-12-01'::date
group by 1
order by 1
(1 row)
*/

```

Turn on debug messages to see what is happening behind the scenes (the prompts sent and the LLM’s responses).

```sql
set client_min_messages to 'DEBUG1';
```

## Supported providers

The `text_to_sql` function uses the Completions API, and searching the semantic catalog uses the Embeddings API. You can use different providers for each component.

| Provider | Completions | Embeddings | API key |
| :---- | :---- | :---- | :---- |
| OpenAI | ✅ | ✅ | `OPENAI_API_KEY` |
| Anthropic | ✅ |  | `ANTHROPIC_API_KEY` |
| Ollama | ✅ | ✅ | n/a |
| VoyageAI |  | ✅ | `VOYAGE_API_KEY` |
| Cohere | ✅ |  | `COHERE_API_KEY` |

## FAQ

* As a developer, how would I track/log what questions my end users are asking?  
  * This is something you’d have to handle at the application level.  
* As a developer, how can end users give thumbs up/down feedback to my application, and how would that feedback go back to pgai for improvement?  
  * Coming soon.  
* Can pgai handle questions that require joining across multiple databases?  
  * You could do this with [foreign data wrappers](https://www.postgresql.org/docs/current/postgres-fdw.html).  
* How does security and privacy work? Who can see what data?  
  * Timescale is trusted by thousands of customers to run demanding production-level software with security at the heart of everything. See our [Security page](https://www.timescale.com/security) for full details on how we keep your data secure.  
  * Schema information and descriptions will go to the LLM provider, and just descriptions will go to the embedding provider. Depending on what provider you’re using, please refer to their privacy policies.   
* As a developer, how do I make sure that my end users can only access data they’re authorized to see?  
  * You could use Postgres [Row Level Security (RLS)](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) to accomplish this. See the example code [here](https://gist.github.com/rahilsondhi/eaafa12a1543d75c0993c094e286beb8)   
* How does pricing work?  
  * pgai is a free Postgres extension.  
  * If you want to use Timescale Cloud to host your Postgres database, please see [timescale.com/pricing](http://timescale.com/pricing).  
  * You will incur charges by the LLM/embedding providers. Please see their Pricing pages.  
* When pgai generates queries, do they automatically get executed?  
  * Not at the moment. It’s the developer’s responsibility to take the SQL query generated by pgai and execute it.  
* What if my end user asks for 10m rows?  
  * You could run an `explain` on the generated query to see if it would be performant or not.  
* What is the latency like?  
  * At minimum, it’s the latency of the LLM provider, plus pgai’s SQL query to search the schema for relevant tables.  
  * If the LLM needs additional information, that will be more LLM round trips and schema searches.  
  * If the LLM hasn’t figured out a solution within 10 interactions, it will abort.  
* How many tables/columns can this support?   
  * There isn’t a known, hard limit. We search your database for tables relevant to the end user’s question and forward those schemas to the LLM.  
* Can I self-host this? Or is it available on Timescale Cloud only?  
  * Yes, you can self-host it, but you’d have to run the [vectorizer workers](https://github.com/timescale/pgai/blob/main/docs/vectorizer/worker.md) as well.  
  * If you’re using Timescale Cloud, we take care of the vectorizer workers for you.
