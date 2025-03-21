import re
from collections.abc import Iterable, Sequence
from functools import cached_property
from typing import Literal, cast

import openai
import tiktoken
from openai import resources
from pydantic import BaseModel
from typing_extensions import override

from ..embeddings import (
    ApiKeyMixin,
    BaseURLMixin,
    BatchApiCaller,
    Document,
    Embedder,
    EmbeddingResponse,
    EmbeddingVector,
    StringDocument,
    Usage,
    logger,
)

TOKEN_CONTEXT_LENGTH_ERROR = "chunk exceeds model context length"

EMBEDDING_MODEL_CONTEXT_LENGTH = {
    "text-embedding-ada-002": 8191,
    "text-embedding-3-small": 8191,
    "text-embedding-3-large": 8191,
}

openai_token_length_regex = re.compile(
    r"This model's maximum context length is (\d+) tokens"
)


class OpenAI(ApiKeyMixin, BaseURLMixin, BaseModel, Embedder):
    """
    Embedder that uses OpenAI's API to embed documents into vector representations.

    Attributes:
        implementation (Literal["openai"]): The literal identifier for this
            implementation.
        model (str): The name of the OpenAI model used for embeddings.
        dimensions (int | None): Optional dimensions for the embeddings.
        user (str | None): Optional user identifier for OpenAI API usage.
    """

    implementation: Literal["openai"]
    model: str
    dimensions: int | None = None
    user: str | None = None

    @cached_property
    def _openai_dimensions(self) -> int | openai.NotGiven:
        if self.model == "text-embedding-ada-002":
            if self.dimensions != 1536:
                raise ValueError("dimensions must be 1536 for text-embedding-ada-002")
            return openai.NOT_GIVEN
        return self.dimensions if self.dimensions is not None else openai.NOT_GIVEN

    @cached_property
    def _openai_user(self) -> str | openai.NotGiven:
        return self.user if self.user is not None else openai.NOT_GIVEN

    @cached_property
    def _embedder(self) -> resources.AsyncEmbeddingsWithRawResponse:
        # TODO: if we move to a generator base approach we should try
        # benchmarking with_streaming_response.
        return openai.AsyncOpenAI(
            base_url=self.base_url, api_key=self._api_key, max_retries=3
        ).embeddings.with_raw_response

    @override
    def _max_chunks_per_batch(self) -> int:
        return 2048

    @override
    def _max_tokens_per_batch(self) -> int:
        return 600_000

    async def call_embed_api(self, documents: list[Document]) -> EmbeddingResponse:
        raw_response = await self._embedder.create(
            input=cast(list[str] | Iterable[Iterable[int]], documents),
            model=self.model,
            dimensions=self._openai_dimensions,
            user=self._openai_user,
            encoding_format="float",
        )
        response = raw_response.http_response.json()
        usage = Usage(
            prompt_tokens=response["usage"]["prompt_tokens"],
            total_tokens=response["usage"]["total_tokens"],
        )
        return EmbeddingResponse(
            embeddings=[r["embedding"] for r in response["data"]], usage=usage
        )

    @cached_property
    def _batcher(self) -> BatchApiCaller[Document]:
        return BatchApiCaller(
            self._max_chunks_per_batch(),
            self._max_tokens_per_batch(),
            self.call_embed_api,
        )

    @override
    async def embed(self, documents: list[StringDocument]) -> Sequence[EmbeddingVector]:
        """
        Embeds a list of documents into vectors using OpenAI's embeddings API.
        The documents are first encoded into tokens before being embedded and
        and truncated to not exceed OpenAI's context window.

        Args:
            documents (list[str]): A list of documents to be embedded.

        Returns:
            Sequence[EmbeddingVector]: The embeddings for each document.
        """
        await logger.adebug(f"Chunks produced: {len(documents)}")
        encoder = self._encoder
        context_length = self._context_length
        is_tokenized = False
        processed_docs: list[Document] = []
        if encoder is not None and context_length is not None:
            # truncate all documents before submitting them to the API
            is_tokenized = True
            for document in documents:
                tokenized = encoder.encode(document)
                if len(tokenized) > context_length:
                    await logger.awarning(
                        f"chunk truncated from {len(tokenized)} to {context_length} tokens"  # noqa
                    )
                    processed_docs.append(tokenized[:context_length])
                else:
                    processed_docs.append(tokenized)
        else:
            processed_docs = cast(list[Document], documents)
        await logger.adebug(f"Chunks produced: {len(documents)}")
        return await self._batcher.batch_chunks_and_embed(processed_docs, is_tokenized)

    @cached_property
    def _encoder(self) -> tiktoken.Encoding | None:
        try:
            encoder = tiktoken.encoding_for_model(self.model)
        except KeyError:
            logger.warning(f"Tokenizer for the model {self.model} not found.")
            return None
        return encoder

    @cached_property
    def _context_length(self) -> int | None:
        return EMBEDDING_MODEL_CONTEXT_LENGTH.get(self.model, None)
