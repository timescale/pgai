
<p align="center">
    <img height="200" src="docs/images/pgai_logo.png#gh-dark-mode-only" alt="pgai"/>
    <img height="200" src="docs/images/pgai_white.png#gh-light-mode-only" alt="pgai"/>
</p>

<div align=center>

<h3>Power your RAG and Agentic applications with PostgreSQL</h3>

<div>
  <a href="https://github.com/timescale/pgai/tree/main/docs"><strong>Docs</strong></a> ·
  <a href="https://discord.gg/KRdHVXAmkp"><strong>Join the pgai Discord!</strong></a> ·
  <a href="https://tsdb.co/gh-pgai-signup"><strong>Try timescale for free!</strong></a> ·
  <a href="https://github.com/timescale/pgai/releases"><strong>Changelog</strong></a>
</div>
</div>
<br/>

A Python library that turns PostgreSQL into the retrieval engine behind robust, production-ready RAG and Agentic applications.

- 🔄 Automatically create vector embeddings from data in PostgreSQL tables as well as documents in S3.  The embeddings are automatically updated as the data changes.

- 🔍 Powerful vector and semantic search with pgvector and pgvectorscale.

- 🛡️ Production-ready out-of-the-box: Supports batch processing for efficient embedding generation, with built-in handling for model failures, rate limits, and latency spikes.

Works with any PostgreSQL database, including Timescale Cloud, Amazon RDS, Supabase and more.

<div align=center>

[![Auto Create and Sync Vector Embeddings in 1 Line of SQL (pgai Vectorizer)](https://github.com/user-attachments/assets/8a71c774-505a-4335-8b34-cdea9dedb558)](https://youtu.be/ZoC2XYol6Zk?si=atI4XPurEifG0pd5)

</div>

### install via pip

```
pip install pgai
```              

# Quick Start

```python
import pgai
pgai.install(DB_URL)

# Create a source table
cur.execute("""
    CREATE TABLE blog (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        text TEXT NOT NULL
    )
""")

# Create a vectorizer
cur.execute("""
    SELECT ai.create_vectorizer(
        'blog'::regclass,
        loading => ai.loading_column(column_name => 'text'),
        embedding => ai.embedding_openai(
            model => 'text-embedding-ada-002',
            dimensions => 1536,
        ),
    )"""
)

# Insert some data
cur.execute("""
    INSERT INTO blog (title, text) VALUES
    ('My first blog post', 'This is the text of my first blog post.'),
    """
)
pgai.vectorizer.run_once()

# Query embeddings
cur.execute("""
    SELECT * FROM blog_embedding_store
    WHERE embedding <=> '[0.1, 0.2, 0.3]'::vector
    ORDER BY embedding <=> '[0.1, 0.2, 0.3]'::vector
    LIMIT 10
""")
```


This section will walk you through the steps to get started with pgai and Ollama using docker and show you the major features of pgai. 

Please note that using Ollama requires a large (>4GB) download of the docker image and model. If you don't want to download so much data, you may want to use the [OpenAI quick start](/docs/vectorizer/quick-start-openai.md) or [VoyageAI quick start](/docs/vectorizer/quick-start-voyage.md) instead.

### Setup

Install PostgreSQL and Ollama if you don't already have them. 

1. **Download the [docker compose file](/examples/docker_compose_pgai_ollama/docker-compose.yml) file.**

    ```
    curl -O https://raw.githubusercontent.com/timescale/pgai/main/examples/docker_compose_pgai_ollama/docker-compose.yml
    ```

1. **Start the docker compose file.**
    ```
    docker compose up -d
    ```


    This will start Ollama and a PostgreSQL instance. 
  
1. **Download the Ollama models.** We'll use the `all-minilm` model for embeddings and the `tinyllama` model for reasoning.

    ```
    docker compose exec ollama ollama pull all-minilm
    docker compose exec ollama ollama pull tinyllama
    ```

### Create a FastAPI app that performs semantic search and RAG over wikipedia articles

You can take a look at a simple [fastAPI Application](/examples/simple_fastapi_app/with_psycopg.py) to see how to
setup an app to perform RAG with pgai Vectorizer. 

To run the app, first download the file and then you can use the following command:

```
fastapi dev with_psycopg.py
```

By going to ` http://0.0.0.0:8000/docs` you can see the API documentation and try out the endpoints provided by the app.

We'll walk you through the main parts of the code below. 

1. **Enable pgai vectorizer on your database**
    During app startup we run the following Python to install the necessary database object in your PostgreSQL database. All the database objects are installed in the `ai` schema. Note that in production use cases, this can also be done via a database migration.
    
    ```python
    pgai.install(DB_URL)
    ```
    
    We also run the vectorizer worker as part of the FastAPI app lifecycle. 
    
    ```python
    worker = Worker(DB_URL)
    task = asyncio.create_task(worker.run())
    ```
    
    In this example, we run the Vectorizer worker inside the FastAPI app for simplicity. You can also run the vectorizer worker outside the FastAPI app, in a separate process or separate container. Please see the [vectorizer worker](/docs/vectorizer/worker.md) documentation for more information.
    
1. **Create the table and load the test dataset**

    We'll create a table named `wiki` from a few rows of the english-language `wikimedia/wikipedia` dataset.
    
    First, we'll create the table using the `create_wiki_table` function:

    <details>
    <summary>Click to see the python code for `create_wiki_table`</summary>
    
    ```python
    async def create_wiki_table():
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS wiki (
                        id SERIAL PRIMARY KEY,
                        url TEXT NOT NULL,
                        title TEXT NOT NULL,
                        text TEXT NOT NULL
                    )
                """)
            await conn.commit()
    ```
    </details>

    Then, we'll load the data from the huggingface dataset using the `load_wiki_articles` function:
    
    <details>
    <summary>Click to see the python code for `load_wiki_articles`</summary>
    
    ```python
    async def load_wiki_articles():
        # to keep the demo fast, we have some simple limits
        num_articles = 10
        max_text_length = 1000
        
        wiki_dataset = load_dataset("wikimedia/wikipedia", "20231101.en", split=f"train", streaming=True)
        
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                for article in wiki_dataset.take(num_articles):
                    await cur.execute(
                        "INSERT INTO wiki (url, title, text) VALUES (%s, %s, %s)",
                        (article['url'], article['title'], article['text'][:max_text_length])
                    )
                await conn.commit()
    ```
    </details>
1. **Create a vectorizer for `wiki`**

    To enable semantic search on the `text` column of the `wiki` table, we need to create vector embeddings for that column.
    We use a vectorizer to automatically create these embeddings and keep them in sync with the data in the  `wiki` table.
    We do this in the `create_vectorizer` function:
    
    <details>
    <summary>Click to see the python code for `create_vectorizer`</summary>
    
    ```python
    async def create_vectorizer():
        vectorizer_statement = CreateVectorizer(
            source="wiki",
            target_table='wiki_embedding_storage',
            loading=LoadingColumnConfig(column_name='text'),
            embedding=EmbeddingOllamaConfig(model='all-minilm', dimensions=384, base_url="http://localhost:11434")
        ).to_sql()
        
        try:
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(vectorizer_statement)
                await conn.commit()
        except Exception as e:
            if "already exists" in str(e):
                # ignore if the vectorizer already exists
                pass
            else:
                raise e
    ```
    </details>
    
    To learn more about vectorizers, see the [vectorizer usage guide](/docs/vectorizer/overview.md).
    
    The `CreateVectorizer` call is a convenience [sql statement builder](/docs/vectorizer/python-integration.md) that helps you build the sql statement to create the vectorizer. You can find the full reference for the sql `create_vectorizer` call in the [vectorizer API reference](/docs/vectorizer/api-reference.md#create-vectorizers).
    
1. **Check the progress of the vectorizer embedding creation**

    In order for the system to be able to perform batch processing when creating the embeddings, and to be able to 
    recover form intermittent model failures, the vectorizer worker creates embeddings asynchronously in the background.
    To check the progress of the vectorizer embedding creation, we can query the `vectorizer_status` view. We do this in the
    `vectorizer_status` function (and endpoint):
    
    <details>
    <summary>Click to see the python code for `vectorizer_status`</summary>
    
    ```python
    @app.get("/vectorizer_status")
    async def vectorizer_status():
        async with pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM ai.vectorizer_status")
                return await cur.fetchall()
    ```
    </details>
    
    You can see the progress by going to the `/vectorizer_status` endpoint. All the embeddings have been created when the `pending_items` column is 0. This should be very quick in this demo.
    
    <details>
    <summary>Click to see the curl command to query the `/vectorizer_status` endpoint</summary>
    
    ```bash
    curl -X 'GET' \
        'http://0.0.0.0:8000/vectorizer_status' \
        -H 'accept: application/json'
    ```
    </details>
    
1. **Search the embeddings using pgvector**

    We'll search the embeddings for the concept of "properties of light" even though these words are not in the text of the articles. This is possible because vector embeddings capture the semantic meaning of the text.
    
    Semantic search is a powerful feature in its own right, but it is also a key component of Retrieval Augmented Generation (RAG).
    
    We first define a function called `_find_relevant_chunks` to find the relevant chunks for a given query. Since we are searching by semantic meaning, a large block of text needs to be broken down into smaller chunks so that the meaning of each chunk is coherent. The vectorizer does this automatically when creating the embeddings and when you search, you get back the chunks that are most relevant to the query.

    <details>
    <summary>Click to see the python code for `_find_relevant_chunks`</summary>
    
    ```python
    @dataclass
    class WikiSearchResult:
        id: int
        url: str
        title: str
        text: str
        chunk: str
        distance: float

    async def _find_relevant_chunks(client: ollama.AsyncClient, query: str, limit: int = 2) -> List[WikiSearchResult]:
        response = await client.embed(model="all-minilm", input=query)
        embedding = np.array(response.embeddings[0])
        
        async with pool.connection() as conn:
            async with conn.cursor(row_factory=class_row(WikiSearchResult)) as cur:
                await cur.execute("""
                    SELECT w.id, w.url, w.title, w.text, w.chunk, w.embedding <=> %s as distance
                    FROM wiki_embedding w
                    ORDER BY distance
                    LIMIT %s
                """, (embedding, limit))
                
                return await cur.fetchall()
    ```
    </details>
    
    This query selects from the `wiki_embedding` view that was created by the vectorizer and which contains all the columns from the `wiki` table plus the `embedding` column which contains the vector embeddings and the `chunk` column which contains the chunked text corresponding to the embedding. In this query, we are returning both the full text of the article and the chunk that is most relevant to the query (different applications may want to return only one or the other).

     The `embedding <=> %s` is a PostgreSQL operator that computes the cosine distance between the stored embedding and the query embedding.
     the greater the distance, the more dissimilar the two vectors are and so we order the results by distance to get the most similar chunks.
    
    This is used in the `/search` endpoint.
    
    <details>
    <summary>Click to see the python code for `/search`</summary>
    
    ```python
    @app.get("/search")
    async def search(query: str):
        client = ollama.AsyncClient(host="http://localhost:11434")
        results = await _find_relevant_chunks(client, query)
        return [asdict(result) for result in results]  
    ```
    </details>
    
    Now you can search through these articles with a query to the search endpoint.
    
    <details>
    <summary>Click to see the curl command to query the `/search` endpoint</summary>
    
    ```bash
    curl -X 'GET' \
        'http://0.0.0.0:8000/search?query=Properties%20of%20Light' \
        -H 'accept: application/json'
    ```
    </details>
    
 1. **Modify your data and have the vectorizer automatically update the embeddings**
 
    We'll create an endpoint called `insert_pgai_article` to add a row about pgai to the `wiki` table and have the vectorizer automatically update the embeddings. This simulates changes to the underlying data.
    
    <details>
    <summary>Click to see the python code for `insert_pgai_article`</summary>
    
    ```python
    @app.post("/insert_pgai_article")
    async def insert_pgai_article():
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO wiki (url, title, text)
                    VALUES (%s, %s, %s)
                """, (
                    "https://en.wikipedia.org/wiki/Pgai",
                    "pgai - Power your AI applications with PostgreSQL",
                    "pgai is a tool to make developing RAG and other AI applications easier..."
                ))
                await conn.commit()
        return {"message": "Article inserted successfully"}
    ```
    </details>
    
    Note: This endpoint simply inserts the text data into the wiki table without having to do anything to create the embeddings. The vectorizer will automatically create the embeddings for the new row without any intervention from you.  The vectorizer will also automatically update the embeddings for the new row when the data changes.
    
    After a few seconds, you can run a search query related to the new entry and see it returned as part of the results:
    
    <details>
    <summary>Click to see the curl command to query the `/search` endpoint</summary>
    
    ```bash
    curl -X 'GET' \
        'http://0.0.0.0:8000/search?query=AI%20Tools' \
        -H 'accept: application/json'
    ```
    </details>
1. **Perform Retrieval Augmented Generation (RAG)**

    In this section, we'll have the LLM answer questions about pgai based on the wiki entry we added by using RAG. The LLM was never trained on the pgai wiki entry, and so it needs data in the database to answer questions about pgai.

    The `rag` endpoint looks as follows:
    
    <details>
    <summary>Click to see the python code for `/rag`</summary>
    
    ```python
    @app.get("/rag")
    async def rag(query: str) -> Optional[str]:
        # Initialize Ollama client
        client = ollama.AsyncClient(host="http://localhost:11434")
        
        #find and format the chunks
        chunks = await _find_relevant_chunks(client, query)
        context = "\n\n".join(f"{article.title}:\n{article.text}" for article, _ in chunks)
        logger.debug(f"Context: {context}")
        
        # Construct prompt with context
        prompt = f"""Question: {query}

    Please use the following context to provide an accurate response:

    {context}

    Answer:"""
                
        # Generate response using Ollama SDK
        response = await client.generate(
            model='tinyllama',
            prompt=prompt,
            stream=False
        )
        
        return response['response']
    ```
    </details>
    
    You can see the RAG response by querying the `/rag` endpoint.
    
    <details>
    <summary>Click to see the curl command to query the `/rag` endpoint</summary>
    
    ```bash
    curl -X 'GET' \
        'http://0.0.0.0:8000/rag?query=What%20is%20pgai' \
        -H 'accept: application/json'
    ```
    </details>

# Features 

Our pgai Python library lets you work with embeddings generated from your data:

* Automatically create and sync vector embeddings for your data using the  ([learn more](/docs/vectorizer/overview.md))
* Search your data using vector and semantic search ([learn more](/docs/vectorizer/overview.md#query-an-embedding))
* Implement Retrieval Augmented Generation as shown above in the [Quick Start](#quick-start)
* Perform high-performance, cost-efficient ANN search on large vector workloads with [pgvectorscale](https://github.com/timescale/pgvectorscale), which complements pgvector.

We also offer a [PostgreSQL extension](/projects/extension/README.md) that can perform LLM model calling directly from SQL. This is often useful for use cases like classification, summarization, and data enrichment on your existing data.

## A configurable vectorizer pipeline

The vectorizer is designed to be flexible and customizable. Each vectorizer defines a pipeline for creating embeddings from your data. The pipeline is defined by a series of components that are applied in sequence to the data:

- **[Loading](/docs/vectorizer/api-reference.md#loading-configuration):** First, you define the source of the data to embed. It can be the data stored directly in a column of the source table or a URI referenced in a column of the source table that points to a file, s3 bucket, etc.
- **[Parsing](/docs/vectorizer/api-reference.md#parsing-configuration):** Then, you define the way the data is parsed if it is a non-text document such as a PDF, HTML, or markdown file.
- **[Chunking](/docs/vectorizer/api-reference.md#chunking-configuration):** Next, you define the way text data is split into chunks.
- **[Formatting](/docs/vectorizer/api-reference.md#formatting-configuration):** Then, for each chunk, you define the way the data is formatted before it is sent for embedding. For example, you can add the title of the document as the first line of the chunk.
- **[Embedding](/docs/vectorizer/api-reference.md#embedding-configuration):** Finally, you specify the LLM provider, model, and the parameters to be used when generating the embeddings.

## Supported embedding models

The following models are supported for embedding:

- [Ollama](/docs/vectorizer/api-reference.md#aiembedding_ollama)
- [OpenAI](/docs/vectorizer/api-reference.md#aiembedding_openai)
- [Voyage AI](/docs/vectorizer/api-reference.md#aiembedding_voyageai)
- [Cohere](/docs/vectorizer/api-reference.md#aiembedding_litellm)
- [Huggingface](/docs/vectorizer/api-reference.md#aiembedding_litellm)
- [Mistral](/docs/vectorizer/api-reference.md#aiembedding_litellm)
- [Azure OpenAI](/docs/vectorizer/api-reference.md#aiembedding_litellm)
- [AWS Bedrock](/docs/vectorizer/api-reference.md#aiembedding_litellm)
- [Vertex AI](/docs/vectorizer/api-reference.md#aiembedding_litellm)

## The importance of a declarative approach to embedding generation

When you define a vectorizer, you define how an embedding is generated from you
data in a *declarative* way (much like an index).  That allows the system to
manage the process of generating and updating the embeddings in the background
for you. The declarative nature of the vectorizer is the "magic sauce" that
allows the system to handle intermittent failures of the LLM and make the system
robust and scalable.

The approach is similar to the way that indexes work in PostgreSQL. When you
create an index, you are essentially declaring that you want to be able to
search for data in a certain way. The system then manages the process of
updating the index as the data changes.
 
# Resources
## Why we built it
- [Vector Databases Are the Wrong Abstraction](https://www.timescale.com/blog/vector-databases-are-the-wrong-abstraction/)
- [pgai: Giving PostgreSQL Developers AI Engineering Superpowers](http://www.timescale.com/blog/pgai-giving-postgresql-developers-ai-engineering-superpowers)

## Quick start guides
- [The quick start with Ollama guide above](#quick-start)
- [Quick start with OpenAI](/docs/vectorizer/quick-start-openai.md)
- [Quick start with VoyageAI](/docs/vectorizer/quick-start-voyage.md)

## Tutorials about pgai vectorizer
- [How to Automatically Create & Update Embeddings in PostgreSQL—With One SQL Query](https://www.timescale.com/blog/how-to-automatically-create-update-embeddings-in-postgresql/)
- [video] [Auto Create and Sync Vector Embeddings in 1 Line of SQL](https://www.youtube.com/watch?v=ZoC2XYol6Zk)
- [Which OpenAI Embedding Model Is Best for Your RAG App With Pgvector?](https://www.timescale.com/blog/which-openai-embedding-model-is-best/)
- [Which RAG Chunking and Formatting Strategy Is Best for Your App With Pgvector](https://www.timescale.com/blog/which-rag-chunking-and-formatting-strategy-is-best/)
- [Parsing All the Data With Open-Source Tools: Unstructured and Pgai](https://www.timescale.com/blog/parsing-all-the-data-with-open-source-tools-unstructured-and-pgai/)


## Contributing
We welcome contributions to pgai! See the [Contributing](/CONTRIBUTING.md) page for more information.


## Get involved

pgai is still at an early stage. Now is a great time to help shape the direction of this project;
we are currently deciding priorities. Have a look at the [list of features](https://github.com/timescale/pgai/issues) we're thinking of working on.
Feel free to comment, expand the list, or hop on the Discussions forum.

To get started, take a look at [how to contribute](./CONTRIBUTING.md)
and [how to set up a dev/test environment](./DEVELOPMENT.md).

## About Timescale

Timescale is a PostgreSQL database company. To learn more visit the [timescale.com](https://www.timescale.com).

Timescale Cloud is a high-performance, developer focused, cloud platform that provides PostgreSQL services
for the most demanding AI, time-series, analytics, and event workloads. Timescale Cloud is ideal for production applications and provides high availability, streaming backups, upgrades over time, roles and permissions, and great security.

[pgai-plpython]: https://github.com/postgres-ai/postgres-howtos/blob/main/0047_how_to_install_postgres_16_with_plpython3u.md
[asdf-postgres]: https://github.com/smashedtoatoms/asdf-postgres
[asdf]: https://github.com/asdf-vm/asdf
[python3]: https://www.python.org/downloads/
[pip]: https://pip.pypa.io/en/stable/installation/#supported-methods
[plpython3u]: https://www.postgresql.org/docs/current/plpython.html
[pgvector]: https://github.com/pgvector/pgvector
[pgvector-install]: https://github.com/pgvector/pgvector?tab=readme-ov-file#installation
[python-virtual-environment]: https://packaging.python.org/en/latest/tutorials/installing-packages/#creating-and-using-virtual-environments
[create-a-new-service]: https://console.cloud.timescale.com/dashboard/create_services
[just]: https://github.com/casey/just
