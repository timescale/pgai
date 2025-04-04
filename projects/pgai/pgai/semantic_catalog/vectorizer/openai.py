import os
from collections.abc import Sequence

from openai import AsyncClient

from pgai.semantic_catalog.vectorizer import EmbedRow, OpenAIConfig


async def embed_batch(config: OpenAIConfig, batch: list[EmbedRow]) -> None:
    api_key: str | None = None
    if config.api_key_name is not None:
        api_key = os.getenv(config.api_key_name)
    client = AsyncClient(api_key=api_key, base_url=config.base_url)  # TODO: cache this?
    response = await client.embeddings.create(
        input=[x.content for x in batch],
        model=config.model,
        dimensions=config.dimensions,
    )
    for emb in response.data:
        batch[emb.index].vector = emb.embedding


async def embed_query(config: OpenAIConfig, query: str) -> Sequence[float]:
    api_key: str | None = None
    if config.api_key_name is not None:
        api_key = os.getenv(config.api_key_name)
    client = AsyncClient(api_key=api_key, base_url=config.base_url)  # TODO: cache this?
    response = await client.embeddings.create(
        input=query,
        model=config.model,
        dimensions=config.dimensions,
    )
    return response.data[0].embedding
