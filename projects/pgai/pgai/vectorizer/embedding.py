"""
Embedding decorator module for pgai vectorizer.

This module provides a decorator for registering custom embedding functions.
"""

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, overload

from .embeddings import ChunkEmbeddingError

# Type definition for embedding functions
EmbeddingFunc = Callable[
    [list[str], dict[str, Any]], Awaitable[Sequence[list[float] | ChunkEmbeddingError]]
]

# Global registry for embedding functions
registered_embeddings: dict[str, EmbeddingFunc] = dict()


@overload
def embedding(func: EmbeddingFunc) -> EmbeddingFunc: ...


@overload
def embedding(
    *, name: str | None = None
) -> Callable[[EmbeddingFunc], EmbeddingFunc]: ...


def embedding(
    func: EmbeddingFunc | None = None,
    *,  # enforce keyword-only arguments
    name: str | None = None,
) -> EmbeddingFunc | Callable[[EmbeddingFunc], EmbeddingFunc]:
    """
    Decorator to register embedding functions in the global registry.
    
    An embedding function takes a list of documents and configuration dictionary 
    and returns a sequence of embedding vectors or errors.
    
    Example:
    ```python
    @embedding(name="my_custom_embedder")
    async def my_embedding_function(
        documents: list[str], config: dict[str, Any]
    ) -> Sequence[list[float] | ChunkEmbeddingError]:
        # Custom embedding logic
        return embeddings
    ```
    """

    def decorator(f: EmbeddingFunc) -> EmbeddingFunc:
        registration_name = name if name is not None else f.__name__
        registered_embeddings[registration_name] = f
        return f

    if func is not None:
        return decorator(func)

    return decorator