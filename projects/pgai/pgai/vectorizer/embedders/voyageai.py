from collections.abc import AsyncGenerator, Callable
from typing import Any, Literal

from pydantic import BaseModel
from tokenizers import Tokenizer
from typing_extensions import override

from ..embeddings import (
    ApiKeyMixin,
    Embedder,
    EmbeddingResponse,
    EmbeddingVector,
    Usage,
    logger,
)


def voyage_max_tokens_per_batch(model: str) -> int:
    # According to https://docs.voyageai.com/docs/embeddings:
    # The total number of tokens in the list is at most:
    # - 1M for voyage-3.5-lite and voyage-3-lite
    # - 320K for voyage-3.5, voyage-3, and voyage-2
    # - 120K for voyage-3-large, voyage-code-3, voyage-large-2-instruct, voyage-finance-2, voyage-multilingual-2, voyage-law-2, voyage-large-2, and voyage-3-lite
    match model:
        case "voyage-3.5-lite" | "voyage-3-lite":
            return 1_000_000
        case "voyage-3.5" | "voyage-2" | "voyage-3":
            return 320_000
        case _:
            return 120_000  # Conservative default for specialized and older models


def voyage_token_counter(
    model: str, api_key: str | None = None
) -> Callable[[str], int] | None:
    # Note: deferred import to avoid import overhead
    import voyageai

    client: voyageai.Client = voyageai.Client(api_key=api_key)
    try:
        tokenizer: Tokenizer = client.tokenizer(model)
        return lambda text: len(tokenizer.encode(text).tokens)
    except BaseException:
        logger.warn(f"Tokenizer for model '{model}' not found")
        return None


class VoyageAI(ApiKeyMixin, BaseModel, Embedder):
    """
    Embedder that uses Voyage AI to embed documents into vector representations.
    Attributes:
        implementation (Literal["voyageai"]): The literal identifier for this
            implementation.
        model (str): The name of the Voyage AU model used for embeddings.
        input_type ("document" | "query" | None): Set the input type of the
            items to be embedded. If set, improves retrieval quality.
        output_dimension (int | None): Set the output dimension for embeddings.
            Supports 256, 512, 1024, or 2048 for newer models (voyage-3.x).
            Lower dimensions reduce storage and improve search speed with slight
            accuracy trade-off (Matryoshka embeddings).
        output_dtype (str | None): Set the output data type for embeddings.
            Supports "float" (default), "int8", "uint8", "binary", "ubinary".
            Quantized types reduce network bandwidth and API costs. Embeddings
            are automatically converted to float for storage in PostgreSQL.

    """

    implementation: Literal["voyageai"]
    model: str
    input_type: Literal["document"] | Literal["query"] | None = None
    output_dimension: int | None = None
    output_dtype: str | None = None

    @override
    async def embed(
        self, documents: list[str]
    ) -> AsyncGenerator[list[EmbeddingVector], None]:
        """
        Embeds a list of documents into vectors using the VoyageAI embeddings API.

        Args:
            documents (list[str]): A list of documents to be embedded.

        Returns:
            Sequence[EmbeddingVector]: The embeddings for each document.
        """
        await logger.adebug(f"Chunks produced: {len(documents)}")
        token_counter = self._token_counter()
        chunk_lengths = (
            [0 for _ in documents]
            if token_counter is None
            else [token_counter(doc) for doc in documents]
        )
        async for embeddings in self.batch_chunks_and_embed(documents, chunk_lengths):
            yield embeddings

    @override
    def _max_chunks_per_batch(self) -> int:
        return 128

    @override
    def _max_tokens_per_batch(self) -> int | None:
        return voyage_max_tokens_per_batch(self.model)

    def _token_counter(self) -> Callable[[str], int] | None:
        return voyage_token_counter(self.model, self._api_key)

    @override
    async def call_embed_api(self, documents: list[str]) -> EmbeddingResponse:
        # Note: deferred import to avoid import overhead
        import voyageai

        # Build API call parameters
        params: dict[str, Any] = {
            "model": self.model,
            "input_type": self.input_type,
        }
        if self.output_dimension is not None:
            params["output_dimension"] = self.output_dimension
        if self.output_dtype is not None:
            params["output_dtype"] = self.output_dtype

        response = await voyageai.AsyncClient(api_key=self._api_key).embed(
            documents,
            **params,
        )
        usage = Usage(
            prompt_tokens=response.total_tokens,
            total_tokens=response.total_tokens,
        )
        return EmbeddingResponse(embeddings=response.embeddings, usage=usage)
