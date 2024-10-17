# pgai

<h3>pgai brings AI workflows to your PostgreSQL database</h3>

[![Discord](https://img.shields.io/badge/Join_us_on_Discord-black?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/KRdHVXAmkp)
[![Try Timescale for free](https://img.shields.io/badge/Try_Timescale_for_free-black?style=for-the-badge&logo=timescale&logoColor=white)](https://tsdb.co/gh-pgai-signup)

</div>

pgai simplifies the process of building [search](https://en.wikipedia.org/wiki/Similarity_search), and
[Retrieval Augmented Generation](https://en.wikipedia.org/wiki/Prompt_engineering#Retrieval-augmented_generation) (RAG) AI applications with PostgreSQL.

pgai brings embedding and generation AI models closer to the database. With pgai, you can now do the following directly from within PostgreSQL in a SQL query:

- Create vector [embeddings](#embed) for your data.
- Retrieve LLM [chat completions](#chat-complete) from models like Claude Sonnet 3.5, OpenAI GPT4o, Cohere Command, and Llama 3 (via Ollama).
- Reason over your data and facilitate use cases like [classification, summarization, and data enrichment](docs/advanced.md) on your existing relational data in PostgreSQL.
