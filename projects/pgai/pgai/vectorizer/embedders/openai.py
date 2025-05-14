import re
from collections.abc import AsyncGenerator
from functools import cached_property
from typing import TYPE_CHECKING, Literal

import ijson  # type: ignore
from pydantic import BaseModel
from typing_extensions import override

if TYPE_CHECKING:
    import openai
    import tiktoken
    from openai import AsyncAPIResponse, resources, types


from ..embeddings import (
    ApiKeyMixin,
    BaseURLMixin,
    Embedder,
    EmbeddingResponse,
    EmbeddingVector,
    Usage,
    logger,
)

TOKEN_CONTEXT_LENGTH_ERROR = "chunk exceeds model context length"

EMBEDDING_MODEL_CONTEXT_LENGTH = {
    "text-embedding-ada-002": 8191,
    "text-embedding-3-small": 8191,
    "text-embedding-3-large": 8191,
}

# ijson reads the input in chunks of buf_size. Since we are wrapping our
# iterator over the read implementation that ijson requires, we explicitly set
# the value when calling ijson methods, and use the same value to iterate over
# the openAI stream response.
#
# The value of 64KB is the default from ijson.
RESPONSE_READ_BUF_SIZE = 64 * 1024

openai_token_length_regex = re.compile(
    r"This model's maximum context length is (\d+) tokens"
)


class ResponseWithRead:
    def __init__(self, response: "AsyncAPIResponse[types.CreateEmbeddingResponse]"):
        self.iter = response.iter_bytes(RESPONSE_READ_BUF_SIZE)

    async def read(self, n: int) -> bytes:
        if n == 0:
            return b""

        return await anext(self.iter)


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
    def _openai_dimensions(self) -> "int | openai.NotGiven":
        # Note: deferred import to avoid import overhead
        import openai

        if self.model == "text-embedding-ada-002":
            if self.dimensions != 1536:
                raise ValueError("dimensions must be 1536 for text-embedding-ada-002")
            return openai.NOT_GIVEN
        return self.dimensions if self.dimensions is not None else openai.NOT_GIVEN

    @cached_property
    def _openai_user(self) -> "str | openai.NotGiven":
        # Note: deferred import to avoid import overhead
        import openai

        return self.user if self.user is not None else openai.NOT_GIVEN

    @cached_property
    def _embedder(self) -> "resources.AsyncEmbeddingsWithStreamingResponse":
        import openai

        return openai.AsyncOpenAI(
            base_url=self.base_url, api_key=self._api_key, max_retries=3
        ).embeddings.with_streaming_response

    @override
    def _max_chunks_per_batch(self) -> int:
        return 2048

    @override
    def _max_tokens_per_batch(self) -> int:
        return 300_000

    @override
    async def call_embed_api(self, documents: list[str]) -> EmbeddingResponse:
        embeddings: list[list[float]] = []
        current_embedding: list[float] = []
        total_tokens = 0
        prompt_tokens = 0
        async with self._embedder.create(
            input=documents,
            model=self.model,
            dimensions=self._openai_dimensions,
            user=self._openai_user,
            encoding_format="float",
        ) as streaming_response:
            # We could simplify by using ijson.item_async:
            #
            # async for value in ijson.items(
            #    ResponseWithRead(raw_response), "data.item.embedding", use_float=True
            # ):
            #     embeddings.append(value)
            #
            # The problem is that `ijson.items` accepts only one prefix, and we
            # need to read data from 2, `data.item.embedding` and `usage`.
            # There's a WIP PR to support this use case:
            # https://github.com/ICRAR/ijson/pull/127
            async for prefix, event, value in ijson.parse_async(
                ResponseWithRead(streaming_response),
                use_float=True,
                buf_size=RESPONSE_READ_BUF_SIZE,
            ):
                if prefix == "data.item.embedding" and event == "start_array":
                    current_embedding = []
                if prefix == "data.item.embedding" and event == "end_array":
                    embeddings.append(current_embedding)
                elif prefix == "data.item.embedding.item" and event == "number":
                    current_embedding.append(value)
                elif prefix == "usage.prompt_tokens" and event == "number":
                    prompt_tokens = value
                elif prefix == "usage.total_tokens" and event == "number":
                    total_tokens = value

        return EmbeddingResponse(
            embeddings=embeddings, usage=Usage(prompt_tokens, total_tokens)
        )

    def _estimate_token_length(self, document: str) -> float:
        """
        Estimates token count based on UTF-8 byte length.
        """

        total_estimated_tokens = 0
        for char in document:
            byte_length = len(char.encode("utf-8"))
            total_estimated_tokens += byte_length * 0.25  # 0.25 tokens per byte

        return total_estimated_tokens

    @override
    async def embed(
        self, documents: list[str]
    ) -> AsyncGenerator[list[EmbeddingVector], None]:
        """
        Embeds a list of documents into vectors using OpenAI's embeddings API.
        The documents are first encoded into tokens before being embedded and
        truncated to not exceed OpenAI's context window.

        Args:
            documents (list[str]): A list of documents to be embedded.

        Returns:
            AsyncGenerator[list[EmbeddingVector], None]: The embeddings for
            each document.
        """
        await logger.adebug(f"Chunks produced: {len(documents)}")
        encoder = self._encoder
        context_length = self._context_length
        if encoder is not None and context_length is not None:
            # truncate all documents before submitting them to the API
            for i, document in enumerate(documents):
                tokenized = encoder.encode(document)
                tokenized_length = len(tokenized)
                if tokenized_length > context_length:
                    await logger.awarning(
                        f"chunk truncated from {len(tokenized)} to {context_length} tokens"  # noqa
                    )
                    documents[i] = encoder.decode(tokenized[:context_length])
        # OpenAIs per batch token limit is using a token estimator instead of actual tokens  # noqa: E501
        # So we are reproducing their token counts
        token_counts = [self._estimate_token_length(document) for document in documents]
        async for embeddings in self.batch_chunks_and_embed(documents, token_counts):
            yield embeddings

    @cached_property
    def _encoder(self) -> "tiktoken.Encoding | None":
        # Note: deferred import to avoid import overhead
        import tiktoken

        try:
            encoder = tiktoken.encoding_for_model(self.model)
        except KeyError:
            logger.warning(f"Tokenizer for the model {self.model} not found.")
            return None
        return encoder

    @cached_property
    def _context_length(self) -> int | None:
        return EMBEDDING_MODEL_CONTEXT_LENGTH.get(self.model, None)
