import os
from collections.abc import Sequence

from openai import AsyncClient

from pgai.semantic_catalog.vectorizer import OpenAIConfig
from pgai.semantic_catalog.vectorizer.models import EmbedRow


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
    if len(response.data) != len(batch):
        raise RuntimeError(
            f"{len(batch)} items sent to openai but {len(response.data)} embeddings returned"  # noqa
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
    if len(response.data) != 1:
        raise RuntimeError(f"expected 1 embedding but got {len(response.data)}")
    return response.data[0].embedding
