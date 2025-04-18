
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

This quickstart illustrates an easy way to enable semantic search and RAG on
your data. **Semantic search** allows you to search for concepts or ideas rather
than keywords. So it will find results that are meaningfully similar to a given query,
even if the words used are different. This seemingly magical ability is made possible
by the LLM-based embedding models create vector embeddings for your data.

Semantic search is a powerful feature in its own right, but it is also a key
component of **Retrieval Augmented Generation (RAG)**.  RAG is a technique that
uses a large language model (LLM) to answer questions using your data instead of
just using the knowledge in the LLM's training data.  It does this by providing
your data as context to the LLM when a question is asked. How does it know which
data to provide? It uses semantic search to find the most relevant data.

**Prerequisites:**
- A PostgreSQL database (click here for docker instructions).
- An OpenAI API key (we use openai for embedding in the quick start, but you can use [multiple providers](#supported-embedding-models)).

Create a `.env` file with the following:

```
OPENAI_API_KEY=<your-openai-api-key>
DB_URL=<your-database-url>
```

run the following code in the same directory as the `.env` file:

```python
import pgai
import psycopg
from dataclasses import dataclass
import os
import dotenv

# load the environment variables for the .env file or from the environment variables
dotenv.load_dotenv()
DB_URL = os.getenv("DB_URL", "postgresql://postgres:postgres@localhost:5432/postgres")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def define_schema(conn: psycopg.AsyncConnection):
    async with conn.cursor() as cur:
        await cur.execute("""
            CREATE TABLE IF NOT EXISTS wiki (
                id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                text TEXT NOT NULL
            )
        """)
        
        # define the vectorizer, which tells the system how to create the embeddings
        # from data in the wiki table.
        await cur.execute("""
            SELECT ai.create_vectorizer(
                'wiki'::regclass,
                loading => ai.loading_column(column_name=>'text'),
                destination => ai.destination_table(target_table=>'wiki_embedding_storage'),
                embedding => ai.embedding_openai(model=>'text-embedding-ada-002', dimensions=>'1536')
            )
        """)   
    await conn.commit()

async def load_wiki_articles_from_huggingface(conn: psycopg.AsyncConnection):
    # to keep the demo fast, we have some simple limits
    num_articles = 10
    max_text_length = 1000
    wiki_dataset = load_dataset("wikimedia/wikipedia", "20231101.en", split="train", streaming=True)
    async with conn.cursor() as cur:
        for article in wiki_dataset.take(num_articles):
            await cur.execute(
                "INSERT INTO wiki (url, title, text) VALUES (%s, %s, %s)",
                (article['url'], article['title'], article['text'][:max_text_length])
            )
    await conn.commit()

# define a dataclass to represent the search results
@dataclass
class WikiSearchResult:
    id: int
    url: str
    title: str
    text: str
    chunk: str
    distance: float

async def _find_relevant_chunks(client: OpenAI, query: str, limit: int = 1) -> List[WikiSearchResult]:
    # create the embedding for the query
    response = await client.embeddings.create({
        model: "text-embedding-ada-002",
        input: query,
        encoding_format: "float",
    })
    embedding = np.array(response.data[0].embedding)
    
    # query the database for the most similar chunks, using standard pgvector syntax
    async with psycopg.AsyncConnection.connect(DB_URL) as conn:
        async with conn.cursor(row_factory=class_row(WikiSearchResult)) as cur:
            await cur.execute("""
                SELECT w.id, w.url, w.title, w.text, w.chunk, w.embedding <=> %s as distance
                FROM wiki_embedding w
                ORDER BY distance
                LIMIT %s
            """, (embedding, limit))
            
            return await cur.fetchall()

def run():
    async with psycopg.AsyncConnection.connect(DB_URL) as conn:
        async with conn.cursor() as cur:
            await define_schema(conn)
            await load_wiki_articles_from_huggingface(conn)
    
    # make the worker run once and create the embeddings
    worker = Worker(DB_URL, once=True)
    worker.run()
   
    # query the embeddings
    client = OpenAI()
    results = await _find_relevant_chunks(client, "Who is the father of computer science?")
    print("Search results 1:")
    print(results)
    
    # insert a new article into the wiki table
    # note that we didn't do anything different during the insert of the new article,
    # to create the embeddings, the vectorizer worker will take care of it.
    async with psycopg.AsyncConnection.connect(DB_URL) as conn:
        async with conn.cursor(row_factory=class_row(WikiSearchResult)) as cur:
            await cur.execute("""
                INSERT INTO wiki (url, title, text) VALUES
                ('https://en.wikipedia.org/wiki/pgai', 'pgai', 'pgai is a Python library that turns PostgreSQL into the retrieval engine behind robust, production-ready RAG and Agentic applications. It does this by automatically creating vector embeddings for your data based on the vectorizer you define.')
            """)
            await conn.commit()
    
    # make the worker run and process the new article. 
    # in a real application, we would not call the worker manually like this,
    # instead, the worker would run continuously in the background and poll for work.
    # You would run it like this:
    # worker = Worker(DB_URL)
    # task = asyncio.create_task(worker.run())
    worker.run()
    
    # query the embeddings again to see the new article
    results = await _find_relevant_chunks(client, "What is pgai?")
    print("Search results 2:")
    print(results)
    
    # perform RAG with the LLM
    query = "What is the main thing pgai does right now?"
    relevant_chunks = await _find_relevant_chunks(client, query)
    context = "\n\n".join(
        f"{chunk.title}:\n{chunk.text}" 
        for chunk in relevant_chunks
    )
    prompt = f"""Question: {query}

Please use the following context to provide an accurate response:   

{context}

Answer:"""

    response = await client.chat.completions.create({
        model: "gpt-3.5-turbo",
        messages: [{ role: "user", content: prompt }],
    })
    print("RAG response:")
    print(response.choices[0].message.content)
    
    
asyncio.run(run())
```

Sample output:

<details>
<summary>Sample output</summary>

```
TODO
```
</details>

## The secret sauce 

The secret sauce of this app is the vectorizer, which automates creating vector embeddings for your data.
In the example above, we create a vectorizer for the `text` column as follows:

```sql
SELECT ai.create_vectorizer(
     'wiki'::regclass,
     loading => ai.loading_column(column_name=>'text'),
     destination => ai.destination_table(target_table=>'wiki_embedding_storage'),
     embedding => ai.embedding_openai(model=>'text-embedding-ada-002', dimensions=>'1536')
    )
```

That call declares how the vectorizer should create embeddings for the `text`
column of the `wiki` table. In this case, it will use the
`text-embedding-ada-002` model from OpenAI to create 1536-dimensional embeddings
and store them in the `wiki_embedding_storage` table. This is a simple example, 
but the vectorizer is [extremely configurable](#a-configurable-vectorizer-pipeline).

Once the vectorizer is created, the vectorizer worker will automatically create
embedddings for all the rows in the `wiki` table, and, more importantly, will
keep the embeddings in sync with the `wiki` table as it changes. Think of it
almost like declaring an index on the `wiki` table, but instead of the database
managing the index datastructure for you, the vectorizer is managing the embeddings. 

The challenge here is that LLMs are slow and somewhat unreliable. Normally, 
there is a lot of MLops you need to perform to make sure your data pipeline
is reliable and robust. With pgai, you can skip all that and focus on building
your application because the vectorizer is managing the embeddings for you.

## Next steps

Look for other quickstarts:
- Quickstart with FastAPI and psycopg [here](/examples/simple_fastapi_app/README.md)

Explore more about the vectorizer:
- Learn more about the [vectorizer](/docs/vectorizer/overview.md) and the [vectorizer worker](/docs/vectorizer/worker.md)
- dive into the vectorizer api [reference](/docs/vectorizer/api-reference.md)

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
