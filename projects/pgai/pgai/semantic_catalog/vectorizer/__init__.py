"""Vectorizer package for creating and managing vector embeddings in the semantic catalog.

This package provides functionality for converting textual content in the semantic
catalog into vector embeddings using various embedding models. It supports multiple
embedding providers including SentenceTransformers, Ollama, and OpenAI.

The vectorizer package is used to generate embeddings for database objects,
SQL examples, and facts in the semantic catalog, enabling vector similarity search.
"""  # noqa: E501

from .vectorizer import (
    EmbeddingConfig,
    OllamaConfig,
    OpenAIConfig,
    SentenceTransformersConfig,
    embedding_config_from_dict,
    vectorize,
    vectorize_query,
)

__all__ = [
    "SentenceTransformersConfig",
    "OllamaConfig",
    "OpenAIConfig",
    "EmbeddingConfig",
    "embedding_config_from_dict",
    "vectorize",
    "vectorize_query",
]
