# Quickstart with demo data

## Overview

We are going to use an open source postgres database named "postgres air" to demonstrate SQL generation.

There are a few setup steps to take first.
We will use pgai to find database objects in the postgres air database and automatically generate natural language descriptions of them using an LLM.
We will then create a semantic catalog in another postgres database, import our descriptions, and embed them.

Once our semantic catalog is loaded with embedded descriptions, we can start generating SQL to answer our questions.

## Prerequisites

* [Python 3](https://www.python.org/downloads/)
* [docker](https://www.docker.com/products/docker-desktop/)
* An [OpenAI key](https://platform.openai.com/api-keys)

## Quickstart Instructions

This quickstart uses the:

* Open source "postgres air" database:  to demonstrate SQL generation.
* pgai: to find database objects in the postgres air database and automatically generate natural language descriptions
  using an LLM.

Using these tools, you create a semantic catalog in another PostgreSQL database, then import and embed the descriptions.
Once the semantic catalog is loaded with embedded descriptions, you start generating SQL to answer questions.

1. **Install pgai**

   ```bash
   pip install "pgai[semantic-catalog]"
   pgai --version
   ```

2. **Run a PostgreSQL container**

   ```bash
   docker run -d --name postgres-air \
       -p 127.0.0.1:5555:5432 \
       -e POSTGRES_HOST_AUTH_METHOD=trust \
       pgvector/pgvector:pg17
   ```

3. **Load the postgres_air dataset**

    1. Unzip [https://github.com/hettie-d/postgres_air](https://drive.google.com/file/d/1C7PVxeYvLDr6n_7qjdA2k0vahv__jMEo/view?usp=drive_link) and put `postgres_air_2024.sql` in your current directory.

    1. Load the postgres_air dataset.

       ```bash
       psql -d "postgres://postgres@localhost:5555/postgres" -v ON_ERROR_STOP=1 -f postgres_air_2024.sql
       ```

   Wait for psql to finish before moving to the next step.

4. **Create a `.env` file**

   In the current working directory, create a `.env` file define the following variables.

   The `TARGET_DB` is the database for which you want an LLM to generate queries.
   The `CATALOG_DB` is the database in which you will create a new semantic catalog.
   We will use the same database for both purposes and thus only specify the `TARGET_DB`.

   ```
   OPENAI_API_KEY="your-OpenAPI-key-goes-here"
   TARGET_DB="postgres://postgres@localhost:5555/postgres"
   ```

5. **Create a semantic catalog**

   First, you need a place to house our semantic descriptions of your database.
   We create a semantic catalog for this.

   You can house multiple semantic catalogs in a single database if you wish.
   Each semantic catalog may have one or more embedding configurations.
   For now, we only need one semantic catalog with a single embedding configuration.

   By default, the first new semantic catalog has the catchy name of, _default_.
   Run the following command to create the semantic catalog and add a default embedding configuration using OpenAI's `text-embedding-3-small`.

   ```bash
   pgai semantic-catalog create
   ```

6. **Generate descriptions of the postgres_air database**

   Now, we need to populate the semantic catalog with information about your database that would be helpful
   to an LLM trying to author SQL statements.

   The following command finds database objects in the postgres_air database, generates descriptions for them
   using an LLM, and outputs a yaml file containing the content for the semantic catalog.

   ```bash
   pgai semantic-catalog describe -f descriptions.yaml
   ```

   Take a look at `descriptions.yaml`. You can manually edit the descriptions to improve them if you wish.


  The semantic catalog can contain:

  - database object descriptions - tables, views, functions, procedures
  - SQL examples - a SQL statement and description
  - facts - standalone pieces of information

  Tables and views are described like this:

   ```yaml
   ---
   schema: postgres_air
   name: aircraft
   type: table
   description: Lists aircraft models with performance characteristics and unique codes.
   columns:
   - name: model
     description: Commercial name of the aircraft model.
   - name: range
     description: Maximum flight range in kilometers.
   - name: class
     description: Airframe class category or configuration indicator.
   - name: velocity
     description: Cruising speed of the aircraft.
   - name: code
     description: Three-character aircraft code serving as the primary key.
   ...
   ```

  Functions and procedures look like this:

   ```yaml
   ---
   schema: postgres_air
   name: advance_air_time
   args:
   - integer
   - pg_catalog.text
   - boolean
   type: procedure
   description: Advances every timestamp/timestamptz column in all tables of the specified
     schema by a given number of weeks, executing or merely displaying the generated
     UPDATE statements according to the p_run flag.
   ...
   ```

  Facts look like this:

   ```yaml
   ---
   type: fact
   description: The names of cities in the city column of the airport table are in all
     capital letters. e.g. "TOKYO"
   ...
   ```

  The `pgai semantic-catalog describe` uses an LLM to get you started, but the better the content in your semantic catalog, the better your results will be.
  The YAML file makes it easy to put a human editor in the loop. You can store the YAML file in version control and manage it with a git-ops strategy if you wish.


7. **Import the descriptions into the semantic catalog in your database**

  The content is useless unless it is available to the LLM, so we need to load it into the database.
  The following command will load the contents of the YAML file into the semantic catalog and generate embeddings.

  ```bash
  pgai semantic-catalog import -f descriptions.yaml
  ```

8. **Now the fun part, search the semantic catalog using natural language**

  With a semantic catalog loaded with descriptions, you can now perform a semantic search using a natural
  language prompt. This finds the database objects, SQL examples, and/or facts that are relevant to the prompt
  provided. For example:

  ```bash
  pgai semantic-catalog search -p "Which passengers have experienced the most flight delays in 2024?"
  ```

9. **See how these search results are rendered to a prompt for an LLM**

  ```bash
  pgai semantic-catalog search -p "Which passengers have experienced the most flight delays in 2024?" --render
  ```

10. **More fun, generate SQL statements on the command line**

  What we really want are SQL queries. The `generate-sql` command uses the prompt rendered from the semantic search to get an LLM to author a query.
  Moreover, the SQL statement is **deterministically checked** using the Postgres query planner (using `EXPLAIN`).
  Thus, not only is the syntax validated but the statement is verified against the actual database objects in the database.
  
  ```bash
  pgai semantic-catalog generate-sql -p "Which passengers have experienced the most flight delays in 2024?"
  ```

11. **Generate SQL statements directly from your Python app**

  While using the command line to author queries is fun, you're more likely going to want to embed this capability in your app.
  The functionality is available as a library too!

  Create a `main.py` file with the contents below:

  ```python
  import os
  import logging
  import asyncio
  import psycopg
  from dotenv import find_dotenv, load_dotenv
  
  import pgai.semantic_catalog as sc
  
  load_dotenv(dotenv_path=find_dotenv(usecwd=True))
  
  logging.basicConfig(
              level="INFO",
              format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
              handlers=[logging.StreamHandler()],
          )
  
  async def main():
      async with await psycopg.AsyncConnection.connect(os.environ["TARGET_DB"]) as con:
          # get a handle to our "default" semantic catalog
          catalog = await sc.from_name(con, "default")
          # generate sql
          response = await catalog.generate_sql(
              con,
              con,
              "openai:gpt-4.1",
              "Which passengers have experienced the most flight delays in 2024?",
          )
  
          print(response.sql_statement)
  
  
  if __name__ == "__main__":
      asyncio.run(main())
  
  ```

  Then, run the following:

  ```bash
  python3 main.py
  ```

## Try a few more questions.

Here is a list of [more questions to try.](more-questions.md)
