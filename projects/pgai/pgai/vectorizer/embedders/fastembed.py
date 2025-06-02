import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Literal

from fastembed import SparseTextEmbedding  # type: ignore
from pgvector.psycopg import SparseVector
from pydantic import BaseModel
from typing_extensions import override

from ..embeddings import Embedder, EmbeddingResponse, EmbeddingVector, logger

DEFAULT_CACHE_DIR = Path.home().joinpath(".cache/fastembed/models")
cache_dir = os.getenv("VECTORIZER_FASTEMBED_CACHE_DIR")
FASTEMBED_CACHE_DIR = DEFAULT_CACHE_DIR if cache_dir is None else Path(cache_dir)


class FastEmbed(BaseModel, Embedder):
    """
    Embedder that uses OpenAI's API to embed documents into vector representations.

    Attributes:
        implementation (Literal["openai"]): The literal identifier for this
            implementation.
        model (str): The name of the OpenAI model used for embeddings.
        dimensions (int | None): Optional dimensions for the embeddings.
        user (str | None): Optional user identifier for OpenAI API usage.
    """

    implementation: Literal["fastembed"]
    model: str
    dimensions: int | None = None
    batch_size: int = 10

    @override
    async def call_embed_api(self, documents: list[str]) -> EmbeddingResponse:
        raise NotImplementedError()

    @override
    async def embed(
        self, documents: list[str]
    ) -> AsyncGenerator[list[EmbeddingVector], None]:
        """
        Embeds a list of documents into vectors using FastEmbed's embeddings API.
        The documents are processed in batches of 256 to optimize performance.

        Args:
            documents (list[str]): A list of documents to be embedded.

        Returns:
            AsyncGenerator[list[EmbeddingVector], None]: The embeddings for
            each document.
        """
        await logger.adebug(f"Chunks produced: {len(documents)}")
        model = SparseTextEmbedding(
            model_name="prithivida/Splade_PP_en_v1",
            cache_dir=FASTEMBED_CACHE_DIR,
            local_files_only=True,
        )

        batch_size = 256
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            embeddings = model.embed(batch, batch_size=self.batch_size, parallel=0)
            yield [SparseVector(e.as_dict(), self.dimensions) for e in embeddings]

    @override
    def _max_chunks_per_batch(self) -> int:
        return 1000
