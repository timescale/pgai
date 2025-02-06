# pgai documentation

Supercharge your PostgreSQL database with AI capabilities. Supports:  

- Automatic creation and synchronization of vector embeddings for your data
- Seamless vector and semantic search  
- Retrieval Augmented Generation (RAG) directly in SQL
- Ability to call out to leading LLMs like OpenAI, Ollama, Cohere, and more via SQL.
- Built-in utilities for dataset loading and processing 

All with the reliability, scalability, and ACID compliance of PostgreSQL.

## pgai install

* [Install pgai with Docker](/docs/install/docker.md): run pgai in a container environment.
* [Install pgai from source](/docs/install/source.md): install pgai from source. 

## pgai Vectorizer

Vectorizer automates the embedding process within your database management by treating embeddings as a declarative, DDL-like feature — like an index.


 **Overview**: [Automate AI embedding with pgai Vectorizer](/docs/vectorizer/overview.md) - a comprehensive overview of Vectorizer features, demonstrating how it streamlines the process of working with vector embeddings in your database.
- **Quickstart guides**:
  * [Vectorizer quickstart for Ollama](/docs/vectorizer/quick-start.md): setup your developer environment, create and run a vectorizer.
  * [Vectorizer quickstart for OpenAI](/docs/vectorizer/quick-start-openai.md): setup your developer environment, create and run a vectorizer using OpenAI.
  * [Vectorizer quickstart for Voyage](/docs/vectorizer/quick-start-voyage.md): setup your developer environment, create and run a vectorizer using Voyage. 
- **References**:
  * [pgai Vectorizer API reference](/docs/vectorizer/api-reference.md): API reference for Vectorizer functions 
  * [Documentation for vectorizer worker](/docs/vectorizer/worker.md): explain how to run vectorizers on a self-hosted PostgreSQL instance.
- **Develop**:
  * [Add a Vectorizer embedding integration](/docs/vectorizer/add-a-embedding-integration.md)


## pgai model calling

Model calling allows you to call out to LLM models from SQL. This lets you leverage the power of LLMs for a variety of tasks, including classification, summarization, moderation, and other forms of data enrichment.

The following models are supported (click on the model to learn more):

| **Model**                                            | **Tokenize** | **Embed** | **Chat Complete** | **Generate** | **Moderate** | **Classify** | **Rerank** |
|------------------------------------------------------|:------------:|:---------:|:-----------------:|:------------:|:------------:|:------------:|:----------:|
| **[Ollama](/docs/model_calling/ollama.md)**                       |              |    ✔️     |        ✔️         |      ✔️      |              |              |            |
| **[OpenAI](/docs/model_calling/openai.md)**                       |     ✔️️      |    ✔️     |        ✔️         |              |      ✔️      |              |            |
| **[Anthropic](/docs/model_calling/anthropic.md)**                 |              |           |                   |      ✔️      |              |              |            |
| **[Cohere](/docs/model_calling/cohere.md)**                       |      ✔️      |    ✔️     |        ✔️         |              |              |      ✔️      |     ✔️     |
| **[Voyage AI](/docs/model_calling/voyageai.md)**                  |              |    ✔️     |                   |              |              |              |            |
| **[Huggingface (with LiteLLM)](/docs/model_calling/litellm.md)**  |              |    ✔️     |                   |              |              |              |            |
| **[Mistral (with LiteLLM)](/docs/model_calling/litellm.md)**      |              |    ✔️     |                   |              |              |              |            |
| **[Azure OpenAI (with LiteLLM)](/docs/model_calling/litellm.md)** |              |    ✔️     |                   |              |              |              |            |
| **[AWS Bedrock (with LiteLLM)](/docs/model_calling/litellm.md)**  |              |    ✔️     |                   |              |              |              |            |
| **[Vertex AI (with LiteLLM)](/docs/model_calling/litellm.md)**    |              |    ✔️     |                   |              |              |              |            |


- **Usage examples**:
  * [Delayed embed](/docs/model_calling/delayed_embed.md): run pgai using pgai or TimescaleDB background actions.
  * [Moderate comments using OpenAI](/docs/model_calling/moderate.md): use triggers or actions to moderate comments using OpenAI.


## pgai utils
  * [Load dataset from Hugging Face](/docs/utils/load_dataset_from_huggingface.md): load datasets from Hugging Face's datasets library directly into your PostgreSQL database.
  * [Chunking](/docs/utils/chunking.md): chunking algorithms you can use from withinSQL.

## pgai operations and security
  * [Secure pgai with user privilages](/docs/security/privileges.md): grant the necessary permissions for a specific user or role to use pgai functionality.
  * [A guide to securely handling API keys](/docs/security/handling-api-keys.md): learn how to securely handle API keys in your database.
