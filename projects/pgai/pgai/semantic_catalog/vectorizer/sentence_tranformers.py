"""SentenceTransformers embedding provider for the semantic catalog vectorizer.

This module implements embedding functionality using SentenceTransformers as the
embedding provider. It provides functions for embedding both batches of content and
individual queries.
"""

import logging
from collections.abc import Sequence
from contextlib import contextmanager

import numpy as np
import numpy.typing as npt
from sentence_transformers import SentenceTransformer

from pgai.semantic_catalog.vectorizer import SentenceTransformersConfig
from pgai.semantic_catalog.vectorizer.models import EmbedRow


@contextmanager
def disable_logging():
    """
    Disable logging for the sentence_transformers and transformers_modules
    libraries.
    """
    st_logger = logging.getLogger("sentence_transformers")
    st_prev_level = st_logger.level
    st_logger.setLevel(logging.ERROR)
    t_logger = logging.getLogger("transformers_modules")
    t_prev_level = t_logger.level
    t_logger.setLevel(logging.ERROR)

    try:
        yield
    finally:
        st_logger.setLevel(st_prev_level)
        t_logger.setLevel(t_prev_level)


async def embed_batch(
    config: SentenceTransformersConfig, batch: list[EmbedRow]
) -> None:
    """Generate embeddings for a batch of content using SentenceTransformers.

    Creates vector embeddings for multiple items using SentenceTransformers and
    updates the vector field in each EmbedRow object with the resulting embedding.

    Args:
        config: Configuration for the SentenceTransformers embedding service.
        batch: List of EmbedRow objects containing content to be embedded.

    Raises:
        AssertionError: If the number of embeddings returned doesn't match the batch size.
    """  # noqa: E501
    st = SentenceTransformer(
        config.model, trust_remote_code=True
    )  # TODO: configurable?
    sentences: list[str] = [x.content for x in batch]
    with disable_logging():
        results: npt.NDArray[np.float64] = st.encode(  # pyright: ignore [reportUnknownMemberType,reportUnknownVariableType]
            sentences=sentences,
            prompt_name=None,
            prompt=None,
            batch_size=len(batch),
            show_progress_bar=False,
            output_value="sentence_embedding",
            precision="float32",
            convert_to_numpy=True,
            convert_to_tensor=False,
            device=None,
            normalize_embeddings=True,
        )
    assert len(results) == len(batch)
    for i, row in enumerate(results):
        batch[i].vector = list(row)


async def embed_query(
    config: SentenceTransformersConfig, query: str
) -> Sequence[float]:
    """Generate an embedding for a single query using SentenceTransformers.

    Creates a vector embedding for a query string using SentenceTransformers.

    Args:
        config: Configuration for the SentenceTransformers embedding service.
        query: The query string to embed.

    Returns:
        A vector embedding (sequence of floats) for the query.

    Raises:
        AssertionError: If the number of embeddings returned is not exactly 1.
    """
    st = SentenceTransformer(
        config.model, trust_remote_code=True
    )  # TODO: configurable?
    sentences: list[str] = [query]
    with disable_logging():
        results: npt.NDArray[np.float64] = st.encode(  # pyright: ignore [reportUnknownMemberType,reportUnknownVariableType]
            sentences=sentences,
            prompt_name=None,
            prompt=None,
            batch_size=1,
            show_progress_bar=False,
            output_value="sentence_embedding",
            precision="float32",
            convert_to_numpy=True,
            convert_to_tensor=False,
            device=None,
            normalize_embeddings=True,
        )
    assert len(results) == 1
    return list(results[0])
