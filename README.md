
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

This quickstart illustrates an east way to enable semantic search and RAG on
your data. Semantic search allows you to search for concepts or ideas rather
than keywords. In this example, you can search for "properties of light" and
will get back results about Albedo, even though those words are not in the text
of the articles. This is possible because LLM-enabled vector embeddings capture
the meaning of the text.

Semantic search is a powerful feature in its own right, but it is also a key
component of Retrieval Augmented Generation (RAG).  RAG is a technique that uses
a large language model (LLM) to answer questions using your data instead of just
using the knowledge in the LLM's training data.  It does this by providing your
data as context to the LLM. How does it know which data to provide? It uses
semantic search to find the most relevant data.

Prerequisites:
- A PostgreSQL database (click here for docker instructions).
- An OpenAI API key (we use openai for embedding in the quick start, but you can use [multiple providers](#supported-embedding-models)).

This quickstart will run through a simple [fastAPI Application](/examples/simple_fastapi_app/with_psycopg.py) 
to see how to setup an app to perform RAG with pgai Vectorizer. The app will
ingest some wikipedia articles, create vector embeddings for them, and allow you
to perform semantic search and RAG. 

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

## The secret sauce 

The secret sauce of this app is the vectorizer, which automates creating vector embeddings for your data. Given a table defined as follows:

```sql
CREATE TABLE wiki (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    text TEXT NOT NULL
);
```

We create a vectorizer for the `text` column as follows:

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

## Application walkthrough  

A full code walkthrough of the application is available in the [application docs](/docs/examples/simple_fastapi_app/README.md).

Here we'll cover a simple usage flow of the application.

First, when the app starts, it automatically ingests the first 10 articles from the `wikimedia/wikipedia` [huggingface dataset](https://huggingface.co/datasets/wikimedia/wikipedia).

Now you can search through these articles with a query to the search endpoint.

```bash
curl -G "http://0.0.0.0:8000/search" \
    --data-urlencode "query=Properties of Light" \
    -H "accept: application/json"
```

We can also use the `/rag` endpoint to answer questions about the articles.

```bash
curl -G "http://0.0.0.0:8000/rag" \
    --data-urlencode "query=What is Albedo?" \
    -H "accept: application/json"
```

Then we can add a new article to the `wiki` table and have the vectorizer automatically update the embeddings.

```bash
curl -X 'POST' \
    'http://0.0.0.0:8000/insert' \
    TODO TODO TODO
    -H 'accept: application/json'
```

In the code, this just does a simple `INSERT` into the `wiki` table. And yet, the vectorizer will automatically create the embeddings for the new row without any intervention from you. 

You can now search for the new article and see it returned as part of the results.

```bash
curl -G "http://0.0.0.0:8000/search" \
    --data-urlencode "query=vector embeddings" \
    -H "accept: application/json"
```

and we can also use the `/rag` endpoint to answer questions about the new article.

```bash
curl -G "http://0.0.0.0:8000/rag" \
    --data-urlencode "query=How does pgai work?" \
    -H "accept: application/json"
```


## Next steps

- See a [full code walkthrough of the application](/docs/examples/simple_fastapi_app/README.md)
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
