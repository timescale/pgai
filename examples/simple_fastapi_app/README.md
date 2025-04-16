# Usage 

This directory contains a simple [fastAPI Application](with_psycopg.py) that
uses pgai Vectorizer to perform semantic search and RAG. The app will ingest
some wikipedia articles, create vector embeddings for them, and allow you to
perform semantic search and RAG. 

To run the app, first download the file with the following command:

```
curl -O https://raw.githubusercontent.com/timescale/pgai/main/examples/simple_fastapi_app/with_psycopg.py
```

Create a `.env` file with the following:

```
OPENAI_API_KEY=<your-openai-api-key>
DB_URL=<your-database-url>
```

and then you can use the following command:

```
fastapi dev with_psycopg.py
```

By going to ` http://0.0.0.0:8000/docs` you can see the API documentation and try out the endpoints provided by the app.

The main endpoints are:
- `/insert`: Insert a row into the wiki table.
- `/search`: Search the articles using semantic search.
- `/rag`: Perform RAG with the LLM.


# Code walkthrough

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