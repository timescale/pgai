# Vectorizer quick start

This page shows you how to create a vectorizer in a self-hosted Postgres instance, then use 
the pgai vectorizer worker to create embeddings from data in your database. To finish off we show how simple it 
is to do semantic search on the embedded data in one query!

## Setup a local developer environment

The local developer environment is a docker configuration you use to develop and test pgai, vectorizers and vectorizer
worker locally. It includes a:
- Postgres deployment image with the TimescaleDB and pgai extensions installed
- pgai vectorizer worker image

On your local machine:

1. **Create the Docker configuration for a local developer environment**

   Copy the following configuration into a file named `compose.yaml`:
    ```yaml
    name: pgai
    services:
      db:
        image: timescale/timescaledb-ha:pg16
        environment:
          POSTGRES_PASSWORD: postgres
          OPENAI_API_KEY: <your-api-key>
        ports:
          - "5432:5432"
        volumes:
          - data:/home/postgres/pgdata/data
      vectorizer-worker:
        image: timescale/pgai-vectorizer-worker:v0.2.1
        environment:
          PGAI_VECTORIZER_WORKER_DB_URL: postgres://postgres:postgres@db:5432/postgres
          OPENAI_API_KEY: <your-api-key>
    volumes:
      data:
    ```

1. **Tune the developer image for your AI provider**

   Replace the instances of `OPENAI_API_KEY` with a key from your AI provider.

1. **Start the database**
   ```shell
    docker compose up -d db
    ```

## Create and run a vectorizer

To create and run a vectorizer, then query the auto-generated embeddings created by the vectorizer:

1. **Connection to the database in your local developer environment**

   - Docker: `docker compose exec -it db psql`
   - psql:  `psql postgres://postgres:postgres@localhost:5432/postgres`

1. **Enable pgai on your database**

    ```sql
    CREATE EXTENSION IF NOT EXISTS ai CASCADE;
    ```

1. **Create the `blog` table with the following schema**
    ```sql
    CREATE TABLE blog (
        id SERIAL PRIMARY KEY,
        title TEXT,
        authors TEXT,
        contents TEXT,
        metadata JSONB
    );
    ```

1. **Insert some data into `blog`**
    ```sql
    INSERT INTO blog (title, authors, contents, metadata)
    VALUES
    ('Getting Started with PostgreSQL', 'John Doe', 'PostgreSQL is a powerful, open source object-relational database system...', '{"tags": ["database", "postgresql", "beginner"], "read_time": 5, "published_date": "2024-03-15"}'),

    ('10 Tips for Effective Blogging', 'Jane Smith, Mike Johnson', 'Blogging can be a great way to share your thoughts and expertise...', '{"tags": ["blogging", "writing", "tips"], "read_time": 8, "published_date": "2024-03-20"}'),

    ('The Future of Artificial Intelligence', 'Dr. Alan Turing', 'As we look towards the future, artificial intelligence continues to evolve...', '{"tags": ["AI", "technology", "future"], "read_time": 12, "published_date": "2024-04-01"}'),

    ('Healthy Eating Habits for Busy Professionals', 'Samantha Lee', 'Maintaining a healthy diet can be challenging for busy professionals...', '{"tags": ["health", "nutrition", "lifestyle"], "read_time": 6, "published_date": "2024-04-05"}'),

    ('Introduction to Cloud Computing', 'Chris Anderson', 'Cloud computing has revolutionized the way businesses operate...', '{"tags": ["cloud", "technology", "business"], "read_time": 10, "published_date": "2024-04-10"}'); 
    ```

4. **Create a vectorizer for `blog`**

    ```sql
    SELECT ai.create_vectorizer(
       'blog'::regclass,
       destination => 'blog_contents_embeddings',
       embedding => ai.embedding_openai('text-embedding-3-small', 768),
       chunking => ai.chunking_recursive_character_text_splitter('contents')
    );
    ```

5. **Run the vectorizer worker**

   When you install pgai on Timescale Cloud, vectorizers are run automatically using TimescaleDB scheduling. 
   For self-hosted, you run a pgai vectorizer worker so the vectorizer can process the data in `blog`. 
   
   In a new terminal, start the vectorizer worker:
   ```shell
   docker compose up -d vectorizer-worker
   ```

1. **Check the vectorizer worker logs** 
   ```shell
   docker compose logs -f vectorizer-worker
   ```

   You see the vectorizer worker pick up the table and process it.
   ```shell
    vectorizer-worker-1  | 2024-10-23 12:56:36 [info     ] running vectorizer             vectorizer_id=1
    ```

1. **See the embeddings in action**

   Run the following search query to retrieve the embeddings:

    ```sql
    SELECT
        chunk,
        embedding <=>  ai.openai_embed('text-embedding-3-small', 'good food', dimensions=>768) as distance
    FROM blog_contents_embeddings
    ORDER BY distance;
    ```

The results look like:

| chunk | distance |
|------|--------|
| Maintaining a healthy diet can be challenging for busy professionals...       | 0.6720892190933228 |
| Blogging can be a great way to share your thoughts and expertise...           | 0.7744888961315155 |
| PostgreSQL is a powerful, open source object-relational database system...    |  0.815629243850708 |
| Cloud computing has revolutionized the way businesses operate...              | 0.8913049921393394 |
| As we look towards the future, artificial intelligence continues to evolve... | 0.9215681301612775 |


That's it, you're done. You now have a table in Postgres that pgai vectorizer automatically creates 
and syncs embeddings for. You can use this vectorizer for semantic search, RAG or any other AI 
app you can think of! If you have any questions, reach out to us on [Discord](https://discord.gg/KRdHVXAmkp).
