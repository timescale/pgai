
<p align="center">
    <img height="200" src="/docs/images/pgai_logo.png" alt="pgai"/>
</p>

<div align=center>

<h3>pgai documentation</h3>

[![Discord](https://img.shields.io/badge/Join_us_on_Discord-black?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/KRdHVXAmkp)
[![Try Timescale for free](https://img.shields.io/badge/Try_Timescale_for_free-black?style=for-the-badge&logo=timescale&logoColor=white)](https://tsdb.co/gh-pgai-signup)
</div>

pgai is a PostgreSQL extension that simplifies data storage and retrieval for [Retrieval Augmented Generation](https://en.wikipedia.org/wiki/Prompt_engineering#Retrieval-augmented_generation) (RAG), and other AI applications.
In particular, it automates the creation and sync of embeddings for your data stored in PostgreSQL, simplifies
[semantic search](https://en.wikipedia.org/wiki/Semantic_search), and allows you to call LLM models from SQL.

The pgai documentation helps you setup, use and develop the projects that make up pgai.  


## pgai Vectorizer

Vectorizer automates the embedding process within your database management by treating embeddings as a declarative,
DDL-like feature — like an index.

- **Get started**:
  * [Vectorizer quickstart for Ollama](/docs/vectorizer-quick-start.md): setup your developer environment, create and run a vectorizer.
  * [Vectorizer quickstart for OpenAI](/docs/vectorizer-quick-start-openai.md): setup your developer environment, create and run a vectorizer using OpenAI.
  * [Vectorizer quickstart for Voyage](/docs/vectorizer-quick-start-voyage.md): setup your developer environment, create and run a vectorizer using Voyage. 
- **Use**:
  * [Automate AI embedding with pgai Vectorizer](/docs/vectorizer.md): a comprehensive overview of Vectorizer features,
    demonstrating how it streamlines the process of working with vector embeddings in your database.
  * [Run vectorizers using pgai vectorizer worker](/docs/vectorizer-worker.md): run vectorizers on a self-hosted TimescaleDB instance.
- **Develop**:
  * [Add a Vectorizer embedding integration](/docs/vectorizer-add-a-embedding-integration.md):
- **Reference**:
  * [pgai Vectorizer API reference](/docs/vectorizer-api-reference.md): API reference for Vectorizer functions 

## pgai model calling

Simplifies data storage and retrieval for AI apps. 

- **Get started**:
  * [Install pgai with Docker](/docs/install_docker.md): run pgai in a container environment.
  * [Setup pgai with Anthropic](/docs/anthropic.md): configure pgai to connect to your Anthropic account.
  * [Setup pgai with Cohere](/docs/cohere.md): configure pgai to connect to your Cohere account.
  * [Setup pgai with Ollama](/docs/ollama.md): configure pgai to connect to your Ollama account.
  * [Setup pgai with OpenAI](/docs/openai.md): configure pgai to connect to your OpenAI account.
  * [Setup pgai with Voyage AI](/docs/voyageai.md): configure pgai to connect to your Voyage AI account.
- **Use**:
  * [Delayed embed](/docs/delayed_embed.md): run pgai using pgai or TimescaleDB background actions.
  * [Load dataset from Hugging Face](/docs/load_dataset_from_huggingface.md): load datasets from Hugging Face's datasets library directly into your PostgreSQL database.
  * [Moderate comments using OpenAI](/docs/moderate.md): use triggers or actions to moderate comments using OpenAI.
  * [Secure pgai with user privilages](/docs/privileges.md): grant the necessary permissions for a specific user or role to use pgai functionality.
- **Develop**:
  * [Install pgai from source](/docs/install_from_source.md): create an environment to develop pgai. 









