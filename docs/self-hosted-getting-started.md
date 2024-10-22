# Quick Start: Run a self-hosted database instance with automatic vectorization

If you want to see how it works, follow these steps to setup 
a self-hosted database instance with automatic embedding vectorization:

## Pre-requisites
- Docker installed on your machine
- An OpenAI API key. You can create one [here](https://platform.openai.com/api-keys).

## Setup

1. Run the following docker-compose file to start a TimescaleDB instance and the Vectorizer worker: 
    ```yaml
    services:
      db:
        image: timescale/timescaledb-ha:cicd-5aefd3c-arm64
        environment:
          POSTGRES_PASSWORD: postgres
          OPENAI_API_KEY: your-api-key
        ports:
          - "5432:5432"
        volumes:
          - ./data:/var/lib/postgresql/data
    
      vectorizer:
        image: timescale/pgai-vectorizer-worker
        environment:
          VECTORIZER_DB_URL: postgres://postgres:postgres@db:5432/postgres
          OPENAI_API_KEY: your-api-key
        depends_on:
          - timescaledb
    ```

2. Connect to your db instance with your DB client of choice. We need to enable the pgai extension and create a simple blog table with the following schema:
    ```sql
    CREATE EXTENSION IF NOT EXISTS ai CASCADE;
    CREATE TABLE blog (
        id SERIAL PRIMARY KEY,
        title TEXT,
        authors TEXT,
        contents TEXT,
        metadata JSONB
    );
    ```
   
3. Insert some data into your new table. E.g. you can run these insert statements:
    ```sql
    INSERT INTO blog (title, authors, contents, metadata)
    VALUES
    ('Getting Started with PostgreSQL', 'John Doe', 'PostgreSQL is a powerful, open source object-relational database system...', '{"tags": ["database", "postgresql", "beginner"], "read_time": 5, "published_date": "2024-03-15"}'),

    ('10 Tips for Effective Blogging', 'Jane Smith, Mike Johnson', 'Blogging can be a great way to share your thoughts and expertise...', '{"tags": ["blogging", "writing", "tips"], "read_time": 8, "published_date": "2024-03-20"}'),

    ('The Future of Artificial Intelligence', 'Dr. Alan Turing', 'As we look towards the future, artificial intelligence continues to evolve...', '{"tags": ["AI", "technology", "future"], "read_time": 12, "published_date": "2024-04-01"}'),

    ('Healthy Eating Habits for Busy Professionals', 'Samantha Lee', 'Maintaining a healthy diet can be challenging for busy professionals...', '{"tags": ["health", "nutrition", "lifestyle"], "read_time": 6, "published_date": "2024-04-05"}'),

    ('Introduction to Cloud Computing', 'Chris Anderson', 'Cloud computing has revolutionized the way businesses operate...', '{"tags": ["cloud", "technology", "business"], "read_time": 10, "published_date": "2024-04-10"}'); 
    ```

4. Now we need to create a vectorizer for the table. The vectorizer worker will pick this one up and create the corresponding embeddings for us:
    ```sql
    SELECT ai.create_vectorizer(
       'blog'::regclass,
       destination => 'blog_contents_embeddings',
       embedding => ai.embedding_openai('text-embedding-3-small', 768),
       chunking => ai.chunking_recursive_character_text_splitter('contents')
    );
    ```
    If you check the logs of the vectorizer worker, you should see that it has picked up the table and is processing it.


5. Now we can run a simple semantic search query to see the embeddings in action:
    ```sql
    SELECT
        chunk,
        embedding <=>  ai.openai_embed('text-embedding-3-small', 'pgai', _dimensions=>768) as distance
    FROM blog_contents_embeddings
    ORDER BY distance
    LIMIT 10;
    ```
 
    The results should look somewhat like this:
    
    | chunk | distance |
    |------|--------|
    | "PostgreSQL is a powerful, open source object-relational database system..." | 0.677 |
    | "As we look towards the future, artificial intelligence continues to evolve..." | 0.781 |
    | Blogging can be a great way to share your thoughts and expertise... | 0.862 |
    | Maintaining a healthy diet can be challenging for busy professionals... | 0.873 |
    | Cloud computing has revolutionized the way businesses operate... | 0.958 |


That's it you're done. You now have a table in postgres for which pgai automatically creates and syncs embeddings for you so you can use it for semantic search or a RAG application or any other AI application you can think of!


