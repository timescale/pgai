# Quickstart with your data

## Overview

This quickstart will help you get up and running with the semantic catalog on your own database.

We will first need to create a semantic catalog in a database.
This semantic catalog will house all the semantic descriptions of your database model.
You can put the semantic catalog in the same database you are describing, or in a separate database.
If you are just trying things out, or if you do not have privileges to make changes to the database you are describing, use a separate database for the semantic catalog.

After creating the semantic catalog, we need to populate it with descriptions of your database.
We will use an LLM to bootstrap these descriptions, but you can edit them as you please.
This content is loaded into the semantic catalog and embedded, making it ready for use.

At this point, you can use pgai both as a CLI tool and as a Python library to generate SQL queries from natural language.

## Prerequisites

* [Python 3](https://www.python.org/downloads/)
* An [OpenAI key](https://platform.openai.com/api-keys)
* A PostgreSQL connection string to the database you want to have an LLM build queries for
* (Optionally) a PostgreSQL connection string to a second database to house the semantic catalog

## Quickstart Instructions


1. **Install pgai**

   ```bash
   pip install "pgai[semantic-catalog]"
   pgai --version
   ```

2. **Create a `.env` file**

   In the current working directory, create a `.env` file define the following variables.
   The `TARGET_DB` is the database for which you want an LLM to generate queries.
   The `CATALOG_DB` is the database in which you will create a new semantic catalog.
   If you want to use one database for both purposes, only specify the `TARGET_DB`.

   ```
   OPENAI_API_KEY="your-OpenAPI-key-goes-here"
   TARGET_DB="postgres://user:password@host:port/database"
   CATALOG_DB="postgres://user:password@host:port/database"
   ```
3. **Create a semantic catalog**

   First, you need a place to house our semantic descriptions of your database.
   We create a semantic catalog for this.

   You can house multiple semantic catalogs in a single database if you wish.
   Each semantic catalog may have one or more embedding configurations.
   For now, we only need one semantic catalog with a single embedding configuration.

   By default, the first new semantic catalog has the catchy name of, _default_.
   Run the following command to create the semantic catalog and add a default embedding configuration using OpenAI's `text-embedding-3-small`.
   It will connect to the `CATALOG_DB`, install pgai into it if it doesn't exist, and configure a semantic catalog.

   ```bash
   pgai semantic-catalog create
   ```

   If you wish to customize the semantic catalog, use the `--help` flag to display your options:

   ```bash
   pgai semantic-catalog create --help
   ```

4. **Generate descriptions of your database**

   Now, we need to populate the semantic catalog with information about your database that would be helpful
   to an LLM trying to author SQL statements.

   The following command connects to your database, finds database objects, generates descriptions for them
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


5. **Import the descriptions into the semantic catalog in your database**

   The content is useless unless it is available to the LLM, so we need to load it into the database.
   The following command will load the contents of the YAML file into the semantic catalog and generate embeddings.

   ```bash
   pgai semantic-catalog import -f descriptions.yaml
   ```

6. **Now the fun part, search the semantic catalog using natural language**

   With a semantic catalog loaded with descriptions, you can now perform a semantic search using a natural
   language prompt. This finds the database objects, SQL examples, and/or facts that are relevant to the prompt
   provided. For example:

   ```bash
   pgai semantic-catalog search -p "Your natural language question goes here!"
   ```

7. **See how these search results are rendered to a prompt for an LLM**

   ```bash
   pgai semantic-catalog search -p "Your natural language question goes here!" --render
   ```

8. **More fun, generate SQL statements on the command line**

  What we really want are SQL queries. The `generate-sql` command uses the prompt rendered from the semantic search to get an LLM to author a query.
  Moreover, the SQL statement is **deterministically checked** using the Postgres query planner (using `EXPLAIN`).
  Thus, not only is the syntax validated but the statement is verified against the actual database objects in the database.

  ```bash
  pgai semantic-catalog generate-sql -p "Your natural language question goes here!"
  ```

9. **Generate SQL statements directly from your Python app**

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
              "Your natural language question goes here!",
          )

          print(response.sql_statement)


  if __name__ == "__main__":
      asyncio.run(main())

  ```

  Then, run the following:

  ```bash
  python3 main.py
  ```
