"""Ollama embedding provider for the semantic catalog vectorizer.

This module implements embedding functionality using Ollama as the embedding provider.
It provides functions for embedding both batches of content and individual queries.
"""

from collections.abc import Sequence

from ollama import AsyncClient

from pgai.semantic_catalog.vectorizer import OllamaConfig
from pgai.semantic_catalog.vectorizer.models import EmbedRow


async def embed_batch(config: OllamaConfig, batch: list[EmbedRow]) -> None:
    """Generate embeddings for a batch of content using Ollama.

    Creates vector embeddings for multiple items using the Ollama API and
    updates the vector field in each EmbedRow object with the resulting embedding.

    Args:
        config: Configuration for the Ollama embedding service.
        batch: List of EmbedRow objects containing content to be embedded.

    Raises:
        RuntimeError: If the number of embeddings returned doesn't match the batch size.
    """
    client = AsyncClient(host=config.base_url)  # TODO: cache this?
    response = await client.embed(config.model, [x.content for x in batch])
    if len(response.embeddings) != len(batch):
        raise RuntimeError(
            f"{len(batch)} items sent to ollama but {len(response.embeddings)} embeddings returned"  # noqa
        )
    for i, embed in enumerate(response.embeddings):
        batch[i].vector = embed


async def embed_query(config: OllamaConfig, query: str) -> Sequence[float]:
    """Generate an embedding for a single query using Ollama.

    Creates a vector embedding for a query string using the Ollama API.

    Args:
        config: Configuration for the Ollama embedding service.
        query: The query string to embed.

    Returns:
        A vector embedding (sequence of floats) for the query.

    Raises:
        RuntimeError: If the number of embeddings returned is not exactly 1.
    """
    client = AsyncClient(host=config.base_url)  # TODO: cache this?
    response = await client.embed(config.model, query)
    if len(response.embeddings) != 1:
        raise RuntimeError(f"expected 1 embedding but got {len(response.embeddings)}")
    return response.embeddings[0]
