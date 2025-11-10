# Vectorizer quick start with VoyageAI

This page shows you how to create a vectorizer and run a semantic search on the automatically embedded data on a self-hosted Postgres instance.
To follow this tutorial you need to have a Voyage AI account API key. You can get one [here](https://www.voyageai.com/).

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
       image: timescale/pgai-vectorizer-worker:latest
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

1. **Install pgai in your database**
   ```shell
   docker compose run --rm --entrypoint "python -m pgai install -d postgres://postgres:postgres@db:5432/postgres" vectorizer-worker
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
      loading => ai.loading_column('contents'),
      embedding => ai.embedding_voyageai(
        'voyage-3.5-lite',  -- or 'voyage-3.5', 'voyage-3-large', 'voyage-code-3', etc.
        1024  -- default dimensions for voyage-3.5-lite
      ),
      destination => ai.destination_table('blog_contents_embeddings')
    );
    ```

    **Available Voyage AI Models:**
    - `voyage-3.5-lite`: Cost & latency optimized, 1024 dims (1M tokens/request) - **Recommended**
    - `voyage-3.5`: General-purpose optimized, 1024 dims (320K tokens/request)
    - `voyage-3-large`: Best for general-purpose & multilingual, 1024 dims (120K tokens/request)
    - `voyage-code-3`: Specialized for code retrieval, 1024 dims (120K tokens/request)
    - `voyage-finance-2`: Finance domain optimized, 1024 dims
    - `voyage-law-2`: Legal document optimized, 1024 dims
    - `voyage-3-lite`: Older model, 512 dims (120K tokens/request)

    **Flexible Dimensions (New!):**
    For voyage-3.x models, you can specify `output_dimension` to reduce storage and improve performance:
    ```sql
    -- Use 256 dimensions for 75% storage reduction
    SELECT ai.create_vectorizer(
      'blog'::regclass,
      loading => ai.loading_column('contents'),
      embedding => ai.embedding_voyageai(
        'voyage-3.5-lite',
        1024,                     -- Schema dimensions
        output_dimension => 256   -- Actual embedding dimensions
      ),
      destination => ai.destination_table('blog_embeddings_compact')
    );
    ```

    **Dimension Trade-offs:**
    - **256 dims**: Fastest search, 75% less storage, minimal accuracy loss
    - **512 dims**: Balanced performance and accuracy
    - **1024 dims**: Default, best accuracy (recommended for most use cases)
    - **2048 dims**: Maximum accuracy for complex tasks

    **Quantization (New!):**
    Use `output_dtype` to reduce network bandwidth and API costs:
    ```sql
    -- Use int8 quantization for 4x bandwidth reduction
    SELECT ai.create_vectorizer(
      'blog'::regclass,
      loading => ai.loading_column('contents'),
      embedding => ai.embedding_voyageai(
        'voyage-3.5-lite',
        1024,
        output_dtype => 'int8'  -- Options: float, int8, uint8, binary, ubinary
      ),
      destination => ai.destination_table('blog_embeddings_quantized')
    );
    ```

    **Quantization Options:**
    - **float**: Default, no compression (4 bytes per dimension)
    - **int8**: Integer quantization, 4x smaller transfer (~1 byte per dim)
    - **uint8**: Unsigned integer quantization, 4x smaller
    - **binary**: Maximum compression, 32x smaller (1 bit per dim)
    - **ubinary**: Unsigned binary, 32x smaller

    Note: Quantized embeddings are automatically converted to float for storage in PostgreSQL, so you get bandwidth savings but not storage savings.

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
       embedding <=>  ai.voyageai_embed('voyage-3.5-lite', 'good food') as distance
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


## Reranking with Voyage AI

Voyage AI also provides reranking capabilities to improve search result relevance. Reranking takes your initial search results and reorders them based on relevance to your query.

### Using the Reranker

**Basic reranking:**
```sql
SELECT *
FROM ai.voyageai_rerank_simple(
  'rerank-2.5',
  'What are best practices for healthy eating?',
  ARRAY[
    'Maintaining a healthy diet can be challenging for busy professionals...',
    'Blogging can be a great way to share your thoughts and expertise...',
    'PostgreSQL is a powerful, open source object-relational database system...',
    'As we look towards the future, artificial intelligence continues to evolve...',
    'Cloud computing has revolutionized the way businesses operate...'
  ],
  api_key => 'your-api-key'
)
ORDER BY relevance_score DESC;
```

**Results:**
| index | document | relevance_score |
|-------|----------|-----------------|
| 0 | Maintaining a healthy diet can be challenging... | 0.9156 |
| 1 | Blogging can be a great way to share... | 0.2341 |
| 4 | Cloud computing has revolutionized... | 0.1023 |
| ... | ... | ... |

**Limit results with top_k:**
```sql
SELECT *
FROM ai.voyageai_rerank_simple(
  'rerank-2.5-lite',
  'healthy eating',
  ARRAY['...'],
  api_key => 'your-api-key',
  top_k => 3
)
ORDER BY relevance_score DESC;
```

### Available Reranker Models

**Current Generation (Recommended):**
| Model | Context Length | Best For |
|-------|---------------|----------|
| `rerank-2.5` | 32K tokens | Quality with multilingual/instruction support |
| `rerank-2.5-lite` | 32K tokens | Latency & quality balance |

**Older Models:**
| Model | Context Length | Notes |
|-------|---------------|-------|
| `rerank-2` | 16K tokens | Legacy |
| `rerank-2-lite` | 8K tokens | Legacy |
| `rerank-1` | 8K tokens | Legacy |
| `rerank-lite-1` | 4K tokens | Legacy |

### Reranker vs Semantic Search

- **Semantic Search** (embeddings): Fast initial retrieval from large datasets
- **Reranking**: Precise relevance scoring for top-k results from semantic search

**Typical workflow:**
1. Use semantic search to get top 100 candidates
2. Use reranker to get the most relevant 5-10 results

---

That's it, you're done. You now have a table in Postgres that pgai vectorizer automatically creates
and syncs embeddings for. You can use this vectorizer for semantic search, RAG or any other AI
app you can think of! If you have any questions, reach out to us on [Discord](https://discord.gg/KRdHVXAmkp).