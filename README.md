
<p align="center">
    <img height="200" src="docs/images/pgai_logo.png#gh-dark-mode-only" alt="pgai"/>
    <img height="200" src="docs/images/pgai_white.png#gh-light-mode-only" alt="pgai"/>
</p>

<div align=center>

<h3>Power your AI applications with PostgreSQL</h3>

<div>
  <a href="https://github.com/timescale/pgai/tree/main/docs"><strong>Docs</strong></a> ·
  <a href="https://discord.gg/KRdHVXAmkp"><strong>Join the pgai Discord!</strong></a> ·
  <a href="https://tsdb.co/gh-pgai-signup"><strong>Try timescale for free!</strong></a> ·
  <a href="https://github.com/timescale/pgai/releases"><strong>Changelog</strong></a>
</div>
</div>
<br/>

Production-Ready AI with PostgreSQL
A Python library for building robust AI applications on PostgreSQL.

- 🔄 Automatically create vector embeddings from your data and keep them synced.

- 🔍 Powerful vector and semantic search

- 🛡️ Production-ready out-of-the-box: batches work for performant embedding generation and handles model failures, rate limits, and latency spikes.

Built to make LLM-powered apps reliable in production.

<div align=center>

[![Auto Create and Sync Vector Embeddings in 1 Line of SQL (pgai Vectorizer)](https://github.com/user-attachments/assets/8a71c774-505a-4335-8b34-cdea9dedb558)](https://youtu.be/ZoC2XYol6Zk?si=atI4XPurEifG0pd5)

</div>

### install via pip

```
pip install pgai
```              

# Quick Start

This section will walk you through the steps to get started with pgai and Ollama using docker and show you the major features of pgai. 

Please note that using Ollama requires a large (>4GB) download of the docker image and model. If you don't want to download so much data, you may want to use the [OpenAI quick start](/docs/vectorizer/quick-start-openai.md) or [VoyageAI quick start](/docs/vectorizer/quick-start-voyage.md) instead.

### Setup

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

You can take a look at a simple [fastAPI Application](/examples/simple_fastapi_app/main.py) to see how to
setup an app to perform RAG with pgai Vectorizer. We'll walk you through the main parts of the code below. 

1. **Enable pgai vectorizer on your database**
    During app startup we run the following Python to install the necessary database object in your PostgreSQL database.
    
    ```python
    pgai.install(DB_URL)
    ```
    
1. **Create a SQLAlchemy model for your dataset**

    We'll create a model for a table named `wiki` from a few rows of the english-language `wikimedia/wikipedia` dataset.
    
    First, we'll create the table:

    ```python
    class Wiki(Base):
        __tablename__ = "wiki"
        
        id: Mapped[int] = mapped_column(primary_key=True)
        url: Mapped[str]
        title: Mapped[str]
        text: Mapped[str]

        # Add vector embeddings for the text field
        text_embeddings = vectorizer_relationship(
            target_table='wiki_embeddings',
            dimensions=384
        )
    ```
    
    Note the `text_embeddings` relationship. This is what defines the vectorizer
    in the model.
    

    Then, we'll load the data from the huggingface dataset:
    
    ```python
    def load_wiki_articles():
        # to keep the demo fast, we have some simple limits
        num_articles = 10
        max_text_length = 1000
        
        # Load and insert Wikipedia dataset from Hugging Face
        wiki_dataset = load_dataset("wikimedia/wikipedia", "20231101.en", split=f"train", streaming=True)
        
        with Session(engine) as session:
            for article in wiki_dataset.take(num_articles):
                wiki = Wiki(
                    url=article['url'],
                    title=article['title'],
                    text=article['text'][:max_text_length]
                )
                session.add(wiki)
            session.commit()
    ```
    
1. **Create a vectorizer for `wiki`**

    To enable semantic search on the `text` column of the `wiki` table, we need to create vector embeddings for that column.
    We use a vectorizer to automatically create these embeddings and keep them in sync with the data in the  `wiki` table.
    
    ```python
    def create_vectorizer():
        vectorizer_statement = CreateVectorizer(
            source="wiki",
            target_table='wiki_embeddings',
            loading=LoadingColumnConfig(column_name='text'),
            embedding=EmbeddingOllamaConfig(model='all-minilm', dimensions=384, base_url="http://localhost:11434")
        ).to_sql()
                
        with Session(engine) as session:
            session.execute(sqlalchemy.text(vectorizer_statement))
            session.commit()
    ```
    
     Related documentation: [vectorizer usage guide](/docs/vectorizer/overview.md) and [vectorizer API reference](/docs/vectorizer/api-reference.md).
    
    
1. **TODO Check the progress of the vectorizer embedding creation**

    ```sql
    select * from ai.vectorizer_status;
    ```
    <details>
    <summary>Click to see the output</summary>
    
    | id | source_table | target_table | view | pending_items |
    |----|--------------|--------------|------|---------------|
    | 1 | public.wiki | public.wiki_embeddings_store | public.wiki_embeddings | 10000 |
    
    </details>
    
    All the embeddings have been created when the `pending_items` column is 0. This may take a few minutes as the model is running locally and not on a GPU.
    
1. **Search the embeddings**

    We'll search the embeddings for the concept of "properties of light" even though these words are not in the text of the articles. This is possible because vector embeddings capture the semantic meaning of the text.
    
    Semantic search is a powerful feature in its own right, but it is also a key component of Retrieval Augmented Generation (RAG).
    
    We first define a function to find the relevant chunks for a given query:

    ```python
    WikiSearchResult = List[Tuple[Wiki, float]]
    
    async def _find_relevant_chunks(client: ollama.AsyncClient, query: str, limit: int = 2) -> WikiSearchResult:
        response = await client.embed(model="all-minilm", input=query)
        embedding = response.embeddings[0]
        with Session(engine) as session:
            # Query both the Wiki model and its embeddings
            result = session.query(
                Wiki,
                Wiki.text_embeddings.embedding.cosine_distance(embedding).label('distance')
            ).join(Wiki.text_embeddings).order_by(
                'distance'
            ).limit(limit).all()
            
        return result
    ```
     
    This query selects from the `Wiki` model using the `text_embeddings` relationship to search through the embeddings. Note: that we can easily combine a search on the embeddings with a filter on any column on the `Wiki` model (e.g. the `title` column).
    
    This is used in the `/search` endpoint as follows:
    ```python
    @app.get("/search")
    async def search(query: str):
        client = ollama.AsyncClient(host="http://localhost:11434")
        
        result = await _find_relevant_chunks(client, query)
        # Convert results to a list of dictionaries
        return [
            {
                "id": article.id,
                "url": article.url,
                "title": article.title,
                "text": article.text,
                "distance": distance
            }
            for article, distance in result
        ]
    ```
    
    Now you can search through these articles with a query to the search endpoint:
    
    ```bash
    curl -X 'GET' \
        'http://0.0.0.0:8000/search?query=Properties%20of%20Light' \
        -H 'accept: application/json'
    ```
    
 1. **Modify your data and have the vectorizer automatically update the embeddings**
 
    We'll add a row about pgai to the `wiki` table and have the vectorizer automatically update the embeddings. This simulates changes to the underlying data.
    
    ```python
    @app.post("/insert_pgai_article")
    async def insert_pgai_article():
        with Session(engine) as session:
            session.add(Wiki(
                url="https://en.wikipedia.org/wiki/Pgai",
                title="pgai - Power your AI applications with PostgreSQL",
                text="pgai is a tool to make developing RAG and other AI applications easier. It makes it simple to give an LLM access to data in your PostgreSQL database by enabling semantic search on your data and using the results as part of the Retrieval Augmented Generation (RAG) pipeline. This allows the LLM to answer questions about your data without needing to being trained on your data.'"
            ))
            session.commit()
        return {"message": "Article inserted successfully"}
    ```
    
    And now you don't need to do anything to update the embeddings. The vectorizer will automatically create the embeddings for the new row without any intervention from you. After a few seconds, you can run a search query related to the new entry and see it returned as part of the results:
    
    ```bash
    curl -X 'GET' \
        'http://0.0.0.0:8000/search?query=AI%20Tools' \
        -H 'accept: application/json'
    ```

1. **Perform Retrieval Augmented Generation (RAG)**

    In this section, we'll have the LLM answer questions about pgai based on the wiki entry we added by using RAG. The LLM was never trained on the pgai wiki entry, and so it needs data in the database to answer questions about pgai.

    The RAG endpoint looks as follows
    
    ```python
    @app.get("/rag")
    async def generate_rag_response(query_text: str) -> Optional[str]:
        # Initialize Ollama client
        client = ollama.AsyncClient(host="http://localhost:11434")
        
        #find and format the chunks
        chunks = await _find_relevant_chunks(client, query_text)
        context = "\n\n".join(f"{article.title}:\n{article.text}" for article, _ in chunks)
        logger.debug(f"Context: {context}")
        
        # Construct prompt with context
        prompt = f"""Question: {query_text}

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
