# Vectorizer quick start

This page shows you how to create an Ollama-based vectorizer in a self-hosted Postgres instance. We also show how simple it is to do semantic search on the automatically embedded data!
If you prefer working with the OpenAI API instead of self-hosting models, you can jump over to the [openai quick start](vectorizer-quick-start-openai.md).

## Setup a local development environment

We use a docker-compose file to set up a development environment, it includes a:
- Postgres deployment image with the TimescaleDB and pgai extensions installed
- pgai vectorizer worker image
- ollama image to host embedding and large language models

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
       ports:
         - "5432:5432"
       volumes:
         - ./data:/var/lib/postgresql/data
     vectorizer-worker:
       image: timescale/pgai-vectorizer-worker:v0.2.1
       environment:
         PGAI_VECTORIZER_WORKER_DB_URL: postgres://postgres:postgres@db:5432/postgres
         OLLAMA_HOST: http://ollama:11434
       command: [ "--poll-interval", "5s" ]
     ollama:
       image: ollama/ollama
    ```

1. **Start the services**
   ```shell
    docker compose up -d
    ```
## Download your embedding model
Before we start we need to tell ollama to download an embedding model so we can use it with pgai. For this example we will use the "nomic-embed-text" model.
To download it into the container simply run:
```
docker compose exec ollama ollama pull nomic-embed-text
```

## Create and run a vectorizer

Now we can create and run a vectorizer. A vectorizer is a pgai concept, it processes data in a table and automatically creates embeddings for it.

1. **Connect to the database in your local developer environment**

   - Docker: `docker compose exec -it pgai psql`
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
         embedding => ai.embedding_ollama('nomic-embed-text', 768),
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
        embedding <=>  ai.ollama_embed('nomic-embed-text', 'good food', host => 'http://ollama:11434') as distance
    FROM blog_contents_embeddings
    ORDER BY distance;
    ```

The results look like:

| chunk                                                                         | distance           |
|-------------------------------------------------------------------------------|--------------------|
| Maintaining a healthy diet can be challenging for busy professionals...       | 0.5030059372474176 |
| PostgreSQL is a powerful, open source object-relational database system...    | 0.5868937074856113 |
| PostgreSQLBlogging can be a great way to share your thoughts and expertise... | 0.5928412342761966 |
| As we look towards the future, artificial intelligence continues to evolve... | 0.6161160890734267 |
| Cloud computing has revolutionized the way businesses operate...              | 0.6664001441252841 |


That's it, you're done. You now have a table in Postgres that pgai vectorizer automatically creates 
and syncs embeddings for. You can use this vectorizer for semantic search, RAG or any other AI 
app you can think of! If you have any questions, reach out to us on [Discord](https://discord.gg/KRdHVXAmkp).
