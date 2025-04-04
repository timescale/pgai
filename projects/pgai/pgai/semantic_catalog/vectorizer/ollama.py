from collections.abc import Sequence

from ollama import AsyncClient

from pgai.semantic_catalog.vectorizer import EmbedRow, OllamaConfig


async def embed_batch(config: OllamaConfig, batch: list[EmbedRow]) -> None:
    client = AsyncClient(host=config.base_url)  # TODO: cache this?
    response = await client.embed(config.model, [x.content for x in batch])
    for i, embed in enumerate(response.embeddings):
        batch[i].vector = embed


async def embed_query(config: OllamaConfig, query: str) -> Sequence[float]:
    client = AsyncClient(host=config.base_url)  # TODO: cache this?
    response = await client.embed(config.model, query)
    return response.embeddings[0]
