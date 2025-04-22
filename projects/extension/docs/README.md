# pgai documentation

Supercharge your PostgreSQL database with AI capabilities. Supports:  

- Ability to call out to leading LLMs like OpenAI, Ollama, Cohere, and more via SQL.
- Built-in utilities for dataset loading and processing 

All with the reliability, scalability, and ACID compliance of PostgreSQL.


## pgai install

* [Install pgai with Docker](install/docker.md): run pgai in a container environment.
* [Install pgai from source](install/source.md): install pgai from source. 


## pgai model calling

Model calling allows you to call out to LLM models from SQL. This lets you leverage the power of LLMs for a variety of tasks, including classification, summarization, moderation, and other forms of data enrichment.

The following models are supported (click on the model to learn more):

| **Model**                                            | **Tokenize** | **Embed** | **Chat Complete** | **Generate** | **Moderate** | **Classify** | **Rerank** |
|------------------------------------------------------|:------------:|:---------:|:-----------------:|:------------:|:------------:|:------------:|:----------:|
| **[Ollama](model_calling/ollama.md)**                       |              |    ✔️     |        ✔️         |      ✔️      |              |              |            |
| **[OpenAI](model_calling/openai.md)**                       |     ✔️️      |    ✔️     |        ✔️         |              |      ✔️      |              |            |
| **[Anthropic](model_calling/anthropic.md)**                 |              |           |                   |      ✔️      |              |              |            |
| **[Cohere](model_calling/cohere.md)**                       |      ✔️      |    ✔️     |        ✔️         |              |              |      ✔️      |     ✔️     |
| **[Voyage AI](model_calling/voyageai.md)**                  |              |    ✔️     |                   |              |              |              |            |
| **[Huggingface (with LiteLLM)](model_calling/litellm.md)**  |              |    ✔️     |                   |              |              |              |            |
| **[Mistral (with LiteLLM)](model_calling/litellm.md)**      |              |    ✔️     |                   |              |              |              |            |
| **[Azure OpenAI (with LiteLLM)](model_calling/litellm.md)** |              |    ✔️     |                   |              |              |              |            |
| **[AWS Bedrock (with LiteLLM)](model_calling/litellm.md)**  |              |    ✔️     |                   |              |              |              |            |
| **[Vertex AI (with LiteLLM)](model_calling/litellm.md)**    |              |    ✔️     |                   |              |              |              |            |


- **Usage examples**:
  * [Delayed embed](model_calling/delayed_embed.md): run pgai using pgai or TimescaleDB background actions.
  * [Moderate comments using OpenAI](model_calling/moderate.md): use triggers or actions to moderate comments using OpenAI.

## pgai utils
  * [Load dataset from Hugging Face](utils/load_dataset_from_huggingface.md): load datasets from Hugging Face's datasets library directly into your PostgreSQL database.
  
## pgai operations and security
  * [Secure pgai with user privilages](security/privileges.md): grant the necessary permissions for a specific user or role to use pgai functionality.
  * [A guide to securely handling API keys](security/handling-api-keys.md): learn how to securely handle API keys in your database.
