from collections.abc import AsyncGenerator, Callable
from typing import Literal

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
    # - 1M for voyage-3-lite
    # - 320K for voyage-3 and voyage-2
    # - 120K for voyage-3-large, voyage-code-3, voyage-large-2-instruct, voyage-finance-2, voyage-multilingual-2, voyage-law-2, and voyage-large-2  # noqa
    match model:
        case "voyage-3-lite":
            return 1_000_000
        case "voyage-2" | "voyage-3":
            return 320_000
        case _:
            return 120_000  # NOTE: This is conservative, but there probably won't be new Voyage models, so...  # noqa


def voyage_token_counter(model: str) -> Callable[[str], int] | None:
    # Note: deferred import to avoid import overhead
    import voyageai

    client: voyageai.Client = voyageai.Client()
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

    """

    implementation: Literal["voyageai"]
    model: str
    input_type: Literal["document"] | Literal["query"] | None = None

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
        return voyage_token_counter(self.model)

    @override
    async def call_embed_api(self, documents: list[str]) -> EmbeddingResponse:
        # Note: deferred import to avoid import overhead
        import voyageai

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
