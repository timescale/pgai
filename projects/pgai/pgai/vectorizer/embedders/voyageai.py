from collections.abc import Sequence
from functools import cached_property
from typing import Literal

import voyageai
import voyageai.error
from pydantic import BaseModel
from typing_extensions import override

from ..embeddings import (
    ApiKeyMixin,
    BatchApiCaller,
    Embedder,
    EmbeddingResponse,
    EmbeddingVector,
    StringDocument,
    Usage,
    logger,
)


class VoyageAI(ApiKeyMixin, BaseModel, Embedder):
    """
    Embedder that uses Voyage AI to embed documents into vector representations.

    Attributes:
        implementation (Literal["voyageai"]): The literal identifier for this
            implementation.
        model (str): The name of the Voyage AU model used for embeddings.
        input_type ("document" | "query" | None): Set the input type of the
            items to be embedded. If set, improves retrieval quality.

    """

    implementation: Literal["voyageai"]
    model: str
    input_type: Literal["document"] | Literal["query"] | None = None

    @override
    async def embed(self, documents: list[str]) -> Sequence[EmbeddingVector]:
        """
        Embeds a list of documents into vectors using the VoyageAI embeddings API.

        Args:
            documents (list[str]): A list of documents to be embedded.

        Returns:
            Sequence[EmbeddingVector | ChunkEmbeddingError]: The embeddings or
            errors for each document.
        """
        await logger.adebug(f"Chunks produced: {len(documents)}")
        return await self._batcher.batch_chunks_and_embed(documents)

    @cached_property
    def _batcher(self) -> BatchApiCaller[StringDocument]:
        return BatchApiCaller(self._max_chunks_per_batch(), self.call_embed_api)

    @override
    def _max_chunks_per_batch(self) -> int:
        return 128

    async def call_embed_api(self, documents: list[str]) -> EmbeddingResponse:
        response = await voyageai.AsyncClient(api_key=self._api_key).embed(
            documents,
            model=self.model,
            input_type=self.input_type,
        )
        usage = Usage(
            prompt_tokens=response.total_tokens,
            total_tokens=response.total_tokens,
        )
        return EmbeddingResponse(embeddings=response.embeddings, usage=usage)
