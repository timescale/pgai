"""OpenAI embedding provider for the semantic catalog vectorizer.

This module implements embedding functionality using OpenAI as the embedding provider.
It provides functions for embedding both batches of content and individual queries.
"""

import os
from collections.abc import Sequence

from openai import AsyncClient

from pgai.semantic_catalog.vectorizer import OpenAIConfig
from pgai.semantic_catalog.vectorizer.models import EmbedRow


async def embed_batch(config: OpenAIConfig, batch: list[EmbedRow]) -> None:
    """Generate embeddings for a batch of content using OpenAI.

    Creates vector embeddings for multiple items using the OpenAI API and
    updates the vector field in each EmbedRow object with the resulting embedding.

    Args:
        config: Configuration for the OpenAI embedding service.
        batch: List of EmbedRow objects containing content to be embedded.

    Raises:
        RuntimeError: If the number of embeddings returned doesn't match the batch size.
    """
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
    """Generate an embedding for a single query using OpenAI.

    Creates a vector embedding for a query string using the OpenAI API.

    Args:
        config: Configuration for the OpenAI embedding service.
        query: The query string to embed.

    Returns:
        A vector embedding (sequence of floats) for the query.

    Raises:
        RuntimeError: If the number of embeddings returned is not exactly 1.
    """
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
