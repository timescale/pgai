<p></p>
<div align=center>

# pgai

<h3>pgai brings AI workflows to your PostgreSQL database</h3>

[![Discord](https://img.shields.io/badge/Join_us_on_Discord-black?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/KRdHVXAmkp)
[![Try Timescale for free](https://img.shields.io/badge/Try_Timescale_for_free-black?style=for-the-badge&logo=timescale&logoColor=white)](https://tsdb.co/gh-pgai-signup)

</div>

pgai simplifies the process of building [search](https://en.wikipedia.org/wiki/Similarity_search), and
[Retrieval Augmented Generation](https://en.wikipedia.org/wiki/Prompt_engineering#Retrieval-augmented_generation) (RAG) AI applications with PostgreSQL.

pgai brings embedding and generation AI models closer to the database. With pgai, you can now do the following directly from within PostgreSQL in a SQL query:

- [Create vector embeddings for your data](https://github.com/timescale/pgai/blob/main/docs/vectorizer-quick-start.md).
- Retrieve LLM chat completions from models like [Claude Sonnet 3.5](https://github.com/timescale/pgai/blob/main/docs/anthropic.md), [OpenAI GPT4o](https://github.com/timescale/pgai/blob/main/docs/openai.md), [Cohere Command](https://github.com/timescale/pgai/blob/main/docs/cohere.md), and [Llama 3 (via Ollama)](https://github.com/timescale/pgai/blob/main/docs/ollama.md).
- Reason over your data and facilitate use cases like [classification, summarization, and data enrichment](https://github.com/timescale/pgai/blob/main/docs/openai.md) on your existing relational data in PostgreSQL.

Here's how to get started with pgai:

- **TL;DR**:
  - [Try out automatic embedding vectorization](https://github.com/timescale/pgai/blob/main/docs/vectorizer-quick-start.md): quickly create embeddings using
    a pre-built Docker developer environment with a self-hosted Postgres instance with pgai and our vectorizer worker
    installed. This takes less than 10 minutes!
- **Everyone**: Use pgai in your PostgreSQL database.
  1. [Install pgai](https://github.com/timescale/pgai/blob/main/README.md#installation) in Timescale Cloud, a pre-built Docker image or from source.
  1. Use pgai to integrate AI from your provider:
     - [Ollama](https://github.com/timescale/pgai/blob/main/docs/ollama.md) - configure pgai for Ollama, then use the model to embed, chat complete and generate.
     - [OpenAI](https://github.com/timescale/pgai/blob/main/docs/openai.md) - configure pgai for OpenAI, then use the model to tokenize, embed, chat complete and moderate. This page also includes advanced examples.
     - [Anthropic](https://github.com/timescale/pgai/blob/main/docs/anthropic.md) - configure pgai for Anthropic, then use the model to generate content.
     - [Cohere](https://github.com/timescale/pgai/blob/main/docs/cohere.md) - configure pgai for Cohere, then use the model to tokenize, embed, chat complete, classify, and rerank.
- **Extension contributor**: Contribute to pgai and improve the project.
  - [Develop and test changes to the pgai extension](https://github.com/timescale/pgai/blob/main/DEVELOPMENT.md).
  - See the [Issues tab](https://github.com/timescale/pgai/issues) for a list of feature ideas to contribute.

**Learn more about pgai:** To learn more about the pgai extension and why we built it, read this blog post [pgai: Giving PostgreSQL Developers AI Engineering Superpowers](http://www.timescale.com/blog/pgai-giving-postgresql-developers-ai-engineering-superpowers).
