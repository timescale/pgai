<p align="center">
    <img height="200" src="https://github.com/timescale/pgai/blob/main/docs/images/pgai_logo.png?raw=true" alt="pgai"/>
</p>

<p></p>
<div align=center>

<h3>pgai allows you to develop RAG, semantic search, and other AI applications directly in PostgreSQL</h3>

[![Discord](https://img.shields.io/badge/Join_us_on_Discord-black?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/KRdHVXAmkp)
[![Try Timescale for free](https://img.shields.io/badge/Try_Timescale_for_free-black?style=for-the-badge&logo=timescale&logoColor=white)](https://tsdb.co/gh-pgai-signup)

</div>

pgai simplifies the process of building [search](https://en.wikipedia.org/wiki/Similarity_search),
[Retrieval Augmented Generation](https://en.wikipedia.org/wiki/Prompt_engineering#Retrieval-augmented_generation) (RAG), and other AI applications with PostgreSQL.

# Overview
The goal of pgai is to make working with AI easier and more accessible to developers. Because data is
the foundation of most AI applications, pgai makes it easier to leverage your data in AI workflows. In particular, pgai supports:

**Working with embeddings generated from your data:**
* Automatically create and sync vector embeddings for your data ([learn more](https://github.com/timescale/pgai/blob/main/README.md#automatically-create-and-sync-llm-embeddings-for-your-data))
* Search your data using vector and semantic search ([learn more](https://github.com/timescale/pgai/blob/main/README.md#search-your-data-using-vector-and-semantic-search))
* Implement Retrieval Augmented Generation inside a single SQL statement ([learn more](https://github.com/timescale/pgai/blob/main/README.md#implement-retrieval-augmented-generation-inside-a-single-sql-statement))
* Perform high-performance, cost-efficient ANN search on large vector workloads with [pgvectorscale](https://github.com/timescale/pgvectorscale), which complements pgvector.

**Leverage LLMs for data processing tasks:**
* Retrieve LLM chat completions from models like Claude Sonnet 3.5, OpenAI GPT4o, Cohere Command, and Llama 3 (via Ollama). ([learn more](https://github.com/timescale/pgai/blob/main/README.md#usage-of-pgai))
* Reason over your data and facilitate use cases like classification, summarization, and data enrichment on your existing relational data in PostgreSQL ([see an example](https://github.com/timescale/pgai/blob/main/docs/openai.md)).

**Learn more about pgai:** To learn more about the pgai extension and why we built it, read
[pgai: Giving PostgreSQL Developers AI Engineering Superpowers](http://www.timescale.com/blog/pgai-giving-postgresql-developers-ai-engineering-superpowers).

**Contributing**: We welcome contributions to pgai! See the [Contributing](https://github.com/timescale/pgai/blob/main/CONTRIBUTING.md) page for more information.

# Getting Started

Here's how to get started with pgai:

For a quick start, try out automatic data embedding using pgai Vectorizer:

 - Try our cloud offering by creating a [free trial account](https://tsdb.co/gh-pgai-signup) and heading over to our pgai Vectorizer [documentation](https://github.com/timescale/pgai/blob/main/docs/vectorizer.md).
 - or check out our [quick start guide](https://github.com/timescale/pgai/blob/main/docs/vectorizer-quick-start.md) to get up and running in less than 10 minutes with a self-hosted Postgres instance.

For other use cases, first [Install pgai](https://github.com/timescale/pgai/blob/main/README.md#installation) in Timescale Cloud, a pre-built Docker image, or from source. Then, choose your own adventure:
  - Automate AI embedding with [pgai Vectorizer](https://github.com/timescale/pgai/blob/main/docs/vectorizer.md).
  -  Use pgai to integrate AI from your provider. Some examples:
     * [Ollama](https://github.com/timescale/pgai/blob/main/docs/ollama.md) - configure pgai for Ollama, then use the model to embed, chat complete and generate.
     * [OpenAI](https://github.com/timescale/pgai/blob/main/docs/openai.md) - configure pgai for OpenAI, then use the model to tokenize, embed, chat complete and moderate. This page also includes advanced examples.
     * [Anthropic](https://github.com/timescale/pgai/blob/main/docs/anthropic.md) - configure pgai for Anthropic, then use the model to generate content.
     * [Cohere](https://github.com/timescale/pgai/blob/main/docs/cohere.md) - configure pgai for Cohere, then use the model to tokenize, embed, chat complete, classify, and rerank.
  - Leverage LLMs for data processing tasks such as classification, summarization, and data enrichment ([see the OpenAI example](https://github.com/timescale/pgai/blob/main/docs/openai.md)).
