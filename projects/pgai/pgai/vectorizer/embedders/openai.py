import re
from collections.abc import Sequence
from functools import cached_property
from typing import Any, Literal

import openai
import tiktoken
from openai import resources
from pydantic import BaseModel
from typing_extensions import override

from ..embeddings import (
    ApiKeyMixin,
    BatchApiCaller,
    ChunkEmbeddingError,
    Embedder,
    EmbeddingResponse,
    EmbeddingVector,
    StringDocument,
    TokenDocument,
    Usage,
    logger,
)

TOKEN_CONTEXT_LENGTH_ERROR = "chunk exceeds model context length"

openai_token_length_regex = re.compile(
    r"This model's maximum context length is (\d+) tokens"
)


class OpenAI(ApiKeyMixin, BaseModel, Embedder):
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
    def _embedder(self) -> resources.AsyncEmbeddings:
        return openai.AsyncOpenAI(api_key=self._api_key, max_retries=3).embeddings

    @override
    def _max_chunks_per_batch(self) -> int:
        return 2048

    async def call_embed_api(self, documents: list[TokenDocument]) -> EmbeddingResponse:
        response = await self._embedder.create(
            input=documents,
            model=self.model,
            dimensions=self._openai_dimensions,
            user=self._openai_user,
            encoding_format="float",
        )
        usage = Usage(
            prompt_tokens=response.usage.prompt_tokens,
            total_tokens=response.usage.total_tokens,
        )
        return EmbeddingResponse(
            embeddings=[r.embedding for r in response.data], usage=usage
        )

    @cached_property
    def _batcher(self) -> BatchApiCaller[TokenDocument]:
        return BatchApiCaller(self._max_chunks_per_batch(), self.call_embed_api)

    @override
    async def embed(
        self, documents: list[StringDocument]
    ) -> Sequence[EmbeddingVector | ChunkEmbeddingError]:
        """
        Embeds a list of documents into vectors using OpenAI's embeddings API.
        The documents are first encoded into tokens before being embedded.

        If a request to generate embeddings fails because one or more chunks
        exceed the model's token limit, the offending chunks are filtered out
        and the request is retried. The returned result will contain a
        ChunkEmbeddingError in place of an EmbeddingVector for the chunks that
        exceeded the model's token limit.

        Args:
            documents (list[str]): A list of documents to be embedded.

        Returns:
            Sequence[EmbeddingVector | ChunkEmbeddingError]: The embeddings or
            errors for each document.
        """
        encoded_documents = await self._encode(documents)
        await logger.adebug(f"Chunks produced: {len(documents)}")
        try:
            return await self._batcher.batch_chunks_and_embed(encoded_documents)
        except openai.BadRequestError as e:
            body = e.body
            if not isinstance(body, dict):
                raise e
            if "message" not in body:
                raise e
            msg: Any = body["message"]
            if not isinstance(msg, str):
                raise e

            m = openai_token_length_regex.match(msg)
            if not m:
                raise e
            model_token_length = int(m.group(1))
            return await self._filter_by_length_and_embed(
                model_token_length, encoded_documents
            )

    async def _filter_by_length_and_embed(
        self, model_token_length: int, encoded_documents: list[list[int]]
    ) -> Sequence[EmbeddingVector | ChunkEmbeddingError]:
        """
        Filters out documents that exceed the model's token limit and embeds
        the valid ones. Chunks that exceed the limit are replaced in the
        response with an ChunkEmbeddingError instead of an EmbeddingVector.

        Args:
            model_token_length (int): The token length limit for the model.
            encoded_documents (list[list[int]]): A list of encoded documents.

        Returns:
            Sequence[EmbeddingVector | ChunkEmbeddingError]: EmbeddingVector
            for the chunks that were successfully embedded, ChunkEmbeddingError
            for the chunks that exceeded the model's token limit.
        """
        valid_documents: list[list[int]] = []
        invalid_documents_idxs: list[int] = []
        for i, doc in enumerate(encoded_documents):
            if len(doc) > model_token_length:
                invalid_documents_idxs.append(i)
            else:
                valid_documents.append(doc)

        assert len(valid_documents) + len(invalid_documents_idxs) == len(
            encoded_documents
        )

        response = await self._batcher.batch_chunks_and_embed(valid_documents)

        embeddings: list[ChunkEmbeddingError | list[float]] = []
        for i in range(len(encoded_documents)):
            if i in invalid_documents_idxs:
                embedding = ChunkEmbeddingError(
                    error=TOKEN_CONTEXT_LENGTH_ERROR,
                    error_details=f"chunk exceeds the {self.model} model context length of {model_token_length} tokens",  # noqa
                )
            else:
                embedding = response.pop(0)
            embeddings.append(embedding)

        return embeddings

    async def _encode(self, documents: list[str]) -> list[list[int]]:
        """
        Encodes a list of documents into a list of tokenized documents, using
        the corresponding encoder for the model.

        Args:
            documents (list[str]): A list of text documents to be tokenized.

        Returns:
            list[list[int]]: A list of tokenized documents.
        """
        total_tokens = 0
        encoded_documents: list[list[int]] = []
        for document in documents:
            if self.model.endswith("001"):
                # See: https://github.com/openai/openai-python/issues/418#issuecomment-1525939500
                # replace newlines, which can negatively affect performance.
                document = document.replace("\n", " ")
            tokenized = self._encoder.encode_ordinary(document)
            total_tokens += len(tokenized)
            encoded_documents.append(tokenized)
        await logger.adebug(f"Total tokens in batch: {total_tokens}")
        return encoded_documents

    @cached_property
    def _encoder(self) -> tiktoken.Encoding:
        return tiktoken.encoding_for_model(self.model)
