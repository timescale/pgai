# Vectorizer quick start with VoyageAI

This page shows you how to create a vectorizer and run a semantic search on the automatically embedded data on a self-hosted Postgres instance.
To follow this tutorial you need to have a Voyage AI account API key. You can get one [here](https://voyageai.com/).

## Setup a local development environment

To set up a development environment for Voyage AI, create a docker-compose file that includes:
- The official TimescaleDB docker image with pgai, pgvectorscale and timescaledb included
- The pgai vectorizer worker image

On your local machine:

1. **Create the Docker configuration for a local developer environment**

   Create the following `docker-compose.yml` in a new directory:
    ```yaml
   name: pgai
   services:
     db:
       image: timescale/timescaledb-ha:pg17
       environment:
         POSTGRES_PASSWORD: postgres
         VOYAGE_API_KEY: your-api-key
       ports:
         - "5432:5432"
       volumes:
         - data:/home/postgres/pgdata/data
     vectorizer-worker:
       image: timescale/pgai-vectorizer-worker:v0.3.0
       environment:
         PGAI_VECTORIZER_WORKER_DB_URL: postgres://postgres:postgres@db:5432/postgres
         VOYAGE_API_KEY: your-api-key
       command: [ "--poll-interval", "5s" ]
   volumes:
     data:
    ```

1. **Start the services**
   ```shell
    docker compose up -d
    ```

## Create and run a vectorizer

Now you can create and run a vectorizer. A vectorizer is a pgai concept, it processes data in a table and automatically creates embeddings for it.

1. **Connect to the database in your local developer environment**

   - Docker: `docker compose exec -it db psql`
   - psql:  `psql postgres://postgres:postgres@localhost:5432/postgres`

1. **Enable pgai on the database**

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
       embedding => ai.embedding_voyageai(
               'voyage-3-lite',
               512
       ),
       chunking => ai.chunking_recursive_character_text_splitter('contents')
   );
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
       embedding <=>  ai.voyageai_embed('voyage-3-lite', 'good food') as distance
   FROM blog_contents_embeddings
   ORDER BY distance;
   ```

The results look like:

| Chunk | Distance |
|--------|-----------|
| Maintaining a healthy diet can be challenging for busy professionals... | 0.6102883386268212 |
| Blogging can be a great way to share your thoughts and expertise... | 0.7245166465928164 |
| PostgreSQL is a powerful, open source object-relational database system... | 0.7789760644464416 |
| As we look towards the future, artificial intelligence continues to evolve... | 0.9036547272308249 |
| Cloud computing has revolutionized the way businesses operate... | 0.9131323552491029 |


That's it, you're done. You now have a table in Postgres that pgai vectorizer automatically creates 
and syncs embeddings for. You can use this vectorizer for semantic search, RAG or any other AI 
app you can think of! If you have any questions, reach out to us on [Discord](https://discord.gg/KRdHVXAmkp).