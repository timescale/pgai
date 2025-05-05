# Text-to-SQL Demo

## Overview

The text-to-sql feature of pgai allows users to ask a natural language question
and have an LLM generate a SQL statement to answer the question.

For example, posing this question to pgai in our demo database

```sql
select ai.text_to_sql('How many flights arrived in Houston, TX in June 2024?');
```

will return the following SQL statement:

```sql
 SELECT COUNT(*) AS num_flights
 FROM postgres_air.flight
 WHERE arrival_airport = 'IAH'
   AND scheduled_arrival >= '2024-06-01'::timestamptz
   AND scheduled_arrival < '2024-07-01'::timestamptz;
```

Running the query returned yields

```text
 num_flights
-------------
        1273
(1 row)
```

In this demo, we will load a database that models air travel. Then, we will take
several steps to prepare pgai to work with the model. We can then pose natural
language questions about air travel and have SQL statements authored for us!

*NOTE:* You will need an OpenAI API key to run this demo.

### How it works: The Semantic Catalog

Postgres has a catalog that maintains information about the database itself.
The details about the tables, views, functions, etc. are maintained in the catalog.
pgai adds the concept of a "semantic catalog." The semantic catalog allows you to
provide natural language descriptions of database objects and example SQL statements
to explain the semantics of your database schema.

pgai uses [Vectorizers](/docs/vectorizer/overview.md) to create and maintain embeddings for each of the 
descriptions stored in the semantic catalog.

The `ai.text_to_sql` function will perform a semantic search of the semantic catalog to
identify database objects and example SQL statements that are relevant to the question
posed. These relevant results are provided to the LLM as context to help it author the SQL to
address the question.

### The dataset

For this demo, we will use the [postgres_air](https://github.com/hettie-d/postgres_air) dataset.
Download the `postgres_air_2024.sql.zip` file from 
[Google Drive](https://drive.google.com/drive/folders/13F7M80Kf_somnjb-mTYAnh1hW1Y_g4kJ) 
and unzip it into this directory.
You will have a `postgres_air_2024.sql` file after unzipping.

If you'd like to see an ERD of the database model, check out 
[the image](https://github.com/hettie-d/postgres_air/blob/main/postgres_air_ERD.png) 
in the postgres_air repo.

## Setup

The entire demo will run in a single docker container. This section describes the
one-time setup steps required to get the demo running. Once these steps have been
executed, you can use pgai to generate SQL to answer any number of natural language
questions.

1. [Build the image and run the container](#build-the-image-and-run-the-container)
2. [Create the demo database](#create-the-demo-database)
3. [Load the dataset](#load-the-dataset)
4. [Install the pgai extension](#install-the-pgai-extension)
5. [Create a Semantic Catalog](#create-a-semantic-catalog)
6. [Set your API key](#set-your-api-key)
7. [Generate Descriptions](#generate-descriptions)
8. [Embed the Descriptions](#embed-the-descriptions)

### Build the image and run the container

First, we need to build the docker image and run it in a container.

_From the root of the pgai repo_, run the following to build a docker image.

```bash
docker build -f projects/extension/Dockerfile --target pgai-test-db -t pgai projects/extension
```

_From the root of the pgai repo_, run a container with the image we built.

NOTE: If you are on Windows, manually substitute \`pwd\` in the command below with the absolute path to the repo.

```bash
docker run -d --name pgai --hostname pgai -e POSTGRES_HOST_AUTH_METHOD=trust \
  --mount type=bind,src=`pwd`/examples/text_to_sql,dst=/demo \
  -p 127.0.0.1:5432:5432 pgai \
  -c shared_preload_libraries='timescaledb, pgextwlist' \
  -c extwlist.extensions='ai,vector'
```

Now, get a shell within the container. The rest of the example will be run from this shell.

```bash
docker exec -w /demo -it pgai /bin/bash
```

### Create the demo database

Run the following to (re)create a `demo` database.

```bash
psql -U postgres -f - <<EOF

drop database if exists demo with (force);
create database demo;

EOF
```

### Load the dataset

Run the following command to restore the `postgres_air` dataset into the `demo` database.

*NOTE:* The database is roughly 8 GB. This step may take a few minutes.

```bash
psql -U postgres -v ON_ERROR_STOP=1 -f postgres_air_2024.sql
```

To verify that the load was successful, run the following command

```bash
psql -U postgres -f - <<EOF
\dt+ postgres_air.*
\l+ postgres
EOF
```
It should return results that look like this. There are ten tables. The sizes may vary slightly but should be similar.

```text
                                           List of relations
    Schema    |      Name      | Type  |  Owner   | Persistence | Access method |  Size   | Description
--------------+----------------+-------+----------+-------------+---------------+---------+-------------
 postgres_air | account        | table | postgres | permanent   | heap          | 84 MB   |
 postgres_air | aircraft       | table | postgres | permanent   | heap          | 16 kB   |
 postgres_air | airport        | table | postgres | permanent   | heap          | 112 kB  |
 postgres_air | boarding_pass  | table | postgres | permanent   | heap          | 2433 MB |
 postgres_air | booking        | table | postgres | permanent   | heap          | 718 MB  |
 postgres_air | booking_leg    | table | postgres | permanent   | heap          | 1061 MB |
 postgres_air | flight         | table | postgres | permanent   | heap          | 67 MB   |
 postgres_air | frequent_flyer | table | postgres | permanent   | heap          | 14 MB   |
 postgres_air | passenger      | table | postgres | permanent   | heap          | 1757 MB |
 postgres_air | phone          | table | postgres | permanent   | heap          | 43 MB   |
(10 rows)

                                                                                    List of databases
   Name   |  Owner   | Encoding | Locale Provider |  Collate   |   Ctype    | Locale | ICU Rules | Access privileges |  Size   | Tablespace |                Description
----------+----------+----------+-----------------+------------+------------+--------+-----------+-------------------+---------+------------+--------------------------------------------
 postgres | postgres | UTF8     | libc            | en_US.utf8 | en_US.utf8 |        |           |                   | 7994 MB | pg_default | default administrative connection database
(1 row)
```

### Install the pgai extension

Run this command to create the pgai extension with the pre-release text-to-sql feature enabled.

```bash
psql -U postgres -v ON_ERROR_STOP=1 -f - <<EOF

drop extension if exists ai cascade;
drop schema if exists ai cascade;
select set_config('ai.enable_feature_flag_text_to_sql', 'true', false);
create extension ai cascade;

EOF
```

### Create a Semantic Catalog

Next, create a semantic catalog.

You need an LLM provider to generate embeddings for the semantic catalog. You can use
any provider supported by Vectorizer. You also need an LLM provider to do chat
completions to do the SQL generation. You do not have to use the same provider for
both; you can mix and match.

The `ai.create_semantic_catalog` function configures the Vectorizers and therefore
takes many of the same parameters. Additionally, it configures which provider and
options will be used for the `text_to_sql` function.

In this demo, we will use OpenAI for both embeddings and SQL generation.

```bash
psql -U postgres -f - <<EOF
select ai.create_semantic_catalog
( embedding=>ai.embedding_openai('text-embedding-3-small', 1024)
, text_to_sql=>ai.text_to_sql_openai(model=>'o3-mini')
);
EOF
```

### Set your API key

There are a [number of supported ways](/projects/extension/docs/security/handling-api-keys.md) to
make your API keys available to pgai. For the purposes of this demo, set the 
OPENAI_API_KEY environment variable in your shell session in the docker container.

```text
export OPENAI_API_KEY="your-key-goes-here"
```

### Generate Descriptions

Next, we need to populate the semantic catalog with descriptions of the elements
of our database model. We could do this manually with pgai functions, but let's
ask an LLM to do it for us. We'll use the [gen_desc.sql](gen_desc.sql) script to
automatically create descriptions for the database objects in the `postgres_air`
schema.

Take a look at the `gen_desc.sql` file. We use the Postgres catalog to find all
the tables and views in the "postgres_air" schema. For each one, we create SQL 
statements that call the `ai.generate_description` and `ai.generate_column_descriptions`
functions from pgai. The `\gexec` metacommand will execute each of these SQL
statements that were created. These functions will invoke the `o3-mini` LLM 
model to author descriptions.

Run it with this command.

NOTE: This is one-time-setup. Once you have descriptions for your database, you
don't have to do this again, unless your model changes. This may take several 
minutes due to the multiple interactions with the LLM.

```bash
PGOPTIONS="-c ai.openai_api_key=$OPENAI_API_KEY" \
  psql -U postgres -v ON_ERROR_STOP=1 \
  -q -X -t -o desc.sql -f gen_desc.sql
```

It will create a file named `desc.sql` with the SQL statements to save
the generated descriptions in the semantic catalog. Review the descriptions and
edit them to your liking. When ready, save the descriptions by running the script:

```bash
psql -U postgres -f desc.sql
```

Run the following command to check that the load was successful

```bash
psql -U postgres -c "select count(*) from ai.semantic_catalog_obj;"
```

It should report 87 rows

```text
 count
-------
    87
(1 row)
```

### Embed the Descriptions

Normally, you'd run the [Vectorizer worker](/docs/vectorizer/worker.md) to 
generate embeddings for the semantic catalog. For the sake of simplicity, we can 
just run the following instead.

NOTE: This is one-time-setup. Once you have embeddings for your descriptions, you
don't have to do this again, unless your descriptions change. This may take several
minutes due to the multiple interactions with the LLM.

```bash
PGOPTIONS="-c ai.openai_api_key=$OPENAI_API_KEY" \
psql -U postgres -v ON_ERROR_STOP=1 -q -X -f gen_embed.sql
```

## Ask an LLM to author SQL statements

Set your OPENAI_API_KEY while connecting to the database

```bash
PGOPTIONS="-c ai.openai_api_key=$OPENAI_API_KEY" psql -U postgres
```

Now, you can ask an LLM to write SQL for you!

*NOTE:* You may get different results from the ones listed below, and you may get
different results each time you ask. The queries returned may not always be valid.
We are actively working on improving this.

```sql
select ai.text_to_sql('How many flights arrived at the IAH airport in June 2024?');
```

It will return a query like the below.

```text
               text_to_sql
-----------------------------------------
 SELECT COUNT(*) AS flight_count        +
 FROM postgres_air.flight               +
 WHERE arrival_airport = 'IAH'          +
   AND scheduled_arrival >= '2024-06-01'+
   AND scheduled_arrival < '2024-07-01';
(1 row)
```

If you are in a YOLO mood, you can execute the SQL written by the LLM by using 
the `\gexec` metacommand in psql instead of a semicolon. This will automatically
execute the results of the prior query as a new query.

```sql
select ai.text_to_sql('How many flights arrived at the IAH airport in June 2024?')
\gexec
```

It will return the actual answer by executing the SQL that was generated!

```text
 flight_count
--------------
         1273
(1 row)
```

If you want to see what is happening under the covers, you can turn on debug log
messages. This will show you the steps that were taken and the messages sent to 
and received from the LLM.

```sql
set client_min_messages to 'debug';
select ai.text_to_sql('How many flights arrived at the IAH airport in June 2024?');
```

The debug messages will show the prompts pgai renders and sends to the LLM. It
will show the responses from the LLM including the tools it chooses to call and
the arguments it provides to the tools. You may see this back and forth interaction
happen multiple times before the LLM provides a final answer in the form of a
SQL statement.

Phrase the question differently and note the difference in the interactions with
the LLM. In this case, we don't provide any airport codes directly. The LLM will
have to figure out how to get an airport code based on the city and state.

```sql
select ai.text_to_sql('How many flights arrived in Houston, TX in June 2024?');
```

It will return something like the following. It had to join the `flight` table
to the `airport` table and filter the `airport` table on `city` and `iso_region`.

```text
                             text_to_sql
----------------------------------------------------------------------
 SELECT COUNT(*) AS total_flights                                    +
 FROM postgres_air.flight AS f                                       +
 JOIN postgres_air.airport AS a ON f.arrival_airport = a.airport_code+
 WHERE f.actual_arrival >= '2024-06-01'                              +
   AND f.actual_arrival < '2024-07-01'                               +
   AND a.city = 'HOUSTON'                                            +
   AND a.iso_region = 'US-TX';
(1 row)
```

Now, try a more difficult question. If you still have debug mode enabled, you will
likely see multiple interactions with the LLM take place before it has enough
context to answer.

```sql
select ai.text_to_sql('How many passengers arrived in Houston, TX in June 2024?');
```

This question required a query that joins four tables, filtering on two, and a
`count distinct`.

```text
                               text_to_sql
---------------------------------------------------------------------------
 SELECT COUNT(DISTINCT bp.passenger_id) AS num_passengers                 +
 FROM postgres_air.boarding_pass bp                                       +
 JOIN postgres_air.booking_leg bl ON bp.booking_leg_id = bl.booking_leg_id+
 JOIN postgres_air.flight f ON bl.flight_id = f.flight_id                 +
 JOIN postgres_air.airport a ON f.arrival_airport = a.airport_code        +
 WHERE a.city = 'HOUSTON'                                                 +
   AND a.iso_region = 'US-TX'                                             +
   AND f.actual_arrival >= '2024-06-01'::timestamptz                      +
   AND f.actual_arrival < '2024-07-01'::timestamptz;
(1 row)
```

### Check out the docs

Check out [the docs](/docs/structured_retrieval/text_to_sql.md) for more information.
