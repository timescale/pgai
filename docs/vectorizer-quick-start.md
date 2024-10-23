# Vectorizer quick start

This page shows you how to create a vectorizer in a self-hosted Postgres instance, then use 
the pgai vectorizer worker to create embeddings from data in your database. To finish off we show how simple it is to do a semantic search query on the embedded data in one query!

## Prerequisites

To follow the steps in this page, you need to:
- [Create a local developer environment](/docs/vectorizer-worker.md#install-the-timescaledb-ha-docker-image)

## Create, run and query a vectorizer

1. **Connection to the database in your local developer environment**

   - Docker: `docker exec -it pgai-db-1 psql -U postgres`
   - psql:  `psql postgres://postgres:postgres@localhost:5432/postgres`

1. **Enable pgai on your database**

    ```sql
    CREATE EXTENSION IF NOT EXISTS ai CASCADE;
    ```

1. **Create a `blog` table with the following schema**
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
       chunking => ai.chunking_recursive_character_text_splitter('contents'),
       scheduling => ai.scheduling_none()
    );
    ```

5. **Run the vectorizer worker**

   When you install pgai on Timescale Cloud, vectorizers are run automatically using TimescaleDB scheduling. 
   For self-hosted, you run a pgai vectorizer worker so the vectorizer can process the data in `blog`. 
   
   In a new terminal, start the vectorizer worker:
   ```shell
   docker-compose up -d vectorizer-worker
   ```
   You see the vectorizer running:
   ```shell
   [+] Running 11/11
   ✔ vectorizer-worker Pulled                                                                                                                                           22.3s 
     ✔ a480a496ba95 Pull complete                                                                                                                                        6.0s 
     ✔ f281ad68d612 Pull complete                                                                                                                                        6.1s 
     ✔ aa77a90b11d9 Pull complete                                                                                                                                        6.5s 
     ✔ 0dd753b657c9 Pull complete                                                                                                                                        6.5s 
     ✔ 38e39325ccaf Pull complete                                                                                                                                        6.5s 
     ✔ 8d50dded1d76 Pull complete                                                                                                                                        6.5s 
     ✔ 5a73fecc1c3f Pull complete                                                                                                                                        6.5s 
     ✔ 03f1e7e22d43 Pull complete                                                                                                                                       20.0s 
     ✔ 33c61f413670 Pull complete                                                                                                                                       20.0s 
     ✔ dc491244f87c Pull complete                                                                                                                                       20.0s 
     [+] Running 1/1
     [+] Running 1/2ai-vectorizer-worker-1  
    ```

1. **Check the vectorizer worker logs** 
   ```shell
   docker-compose logs -f vectorizer-worker
   ```

   You see the vectorizer worker pick up the table and process it.
   ```shell
    vectorizer-worker-1  | 2024-10-23 12:56:36 [info     ] running vectorizer             vectorizer_id=1
    ```
   
    To see the status of your vectorizer queue, use the following query 
    `select ai.vectorizer_queue_pending(1) \watch`. To see the the database logs run 
    `docker-compose logs -f db`. 

1. **See the embeddings in action**

   Run the following search query to retrieve the embeddings:

    ```sql
    SELECT
        chunk,
        embedding <=>  ai.openai_embed('text-embedding-3-small', 'pgai', _dimensions=>768) as distance
    FROM blog_contents_embeddings
    ORDER BY distance;
    ```

The results look like:

| chunk | distance |
|------|--------|
| "PostgreSQL is a powerful, open source object-relational database system..." | 0.677 |
| "As we look towards the future, artificial intelligence continues to evolve..." | 0.781 |
| Blogging can be a great way to share your thoughts and expertise... | 0.862 |
| Maintaining a healthy diet can be challenging for busy professionals... | 0.873 |
| Cloud computing has revolutionized the way businesses operate... | 0.958 |


That's it, you're done. You now have a table in Postgres that pgai vectorizer automatically creates 
and syncs embeddings for. You can use this vectorizer for semantic search, RAG or any other AI 
app you can think of! If you have any questions, reach out to us on [Discord](https://discord.gg/KRdHVXAmkp).

