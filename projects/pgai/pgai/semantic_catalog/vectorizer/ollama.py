from collections.abc import Sequence

from ollama import AsyncClient

from pgai.semantic_catalog.vectorizer import OllamaConfig
from pgai.semantic_catalog.vectorizer.models import EmbedRow


async def embed_batch(config: OllamaConfig, batch: list[EmbedRow]) -> None:
    client = AsyncClient(host=config.base_url)  # TODO: cache this?
    response = await client.embed(config.model, [x.content for x in batch])
    if len(response.embeddings) != len(batch):
        raise RuntimeError(
            f"{len(batch)} items sent to ollama but {len(response.embeddings)} embeddings returned"  # noqa
        )
    for i, embed in enumerate(response.embeddings):
        batch[i].vector = embed


async def embed_query(config: OllamaConfig, query: str) -> Sequence[float]:
    client = AsyncClient(host=config.base_url)  # TODO: cache this?
    response = await client.embed(config.model, query)
    if len(response.embeddings) != 1:
        raise RuntimeError(f"expected 1 embedding but got {len(response.embeddings)}")
    return response.embeddings[0]
