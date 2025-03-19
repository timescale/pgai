import io
import json
import re
from collections.abc import Iterable, Sequence
from functools import cached_property
from typing import Any, Literal, cast

import openai
import tiktoken
from openai import AsyncOpenAI, resources
from openai.types.batch import Batch
from pydantic import BaseModel
from typing_extensions import override

from ..embeddings import (
    ApiKeyMixin,
    AsyncBatch,
    AsyncBatchEmbedder,
    BaseURLMixin,
    BatchApiCaller,
    ChunkEmbeddingError,
    Document,
    DocumentWithID,
    Embedder,
    EmbeddingResponse,
    EmbeddingVector,
    StringDocument,
    Usage,
    logger,
)

TOKEN_CONTEXT_LENGTH_ERROR = "chunk exceeds model context length"

openai_token_length_regex = re.compile(
    r"This model's maximum context length is (\d+) tokens"
)


class OpenAI(ApiKeyMixin, BaseURLMixin, BaseModel, Embedder, AsyncBatchEmbedder):
    """
    Embedder that uses OpenAI's API to embed documents into vector representations.

    Attributes:
        implementation (Literal["openai"]): The literal identifier for this
            implementation.
        model (str): The name of the OpenAI model used for embeddings.
        dimensions (int | None): Optional dimensions for the embeddings.
        user (str | None): Optional user identifier for OpenAI API usage.
        async_batch_enabled (bool): If True, then use the async batch API.
    """

    implementation: Literal["openai"]
    model: str
    dimensions: int | None = None
    user: str | None = None
    async_batch_enabled: bool = False

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
    def _client(self) -> AsyncOpenAI:
        return AsyncOpenAI(base_url=self.base_url, api_key=self._api_key, max_retries=3)

    @cached_property
    def _embedder(self) -> resources.AsyncEmbeddings:
        return self._client.embeddings

    @override
    def _max_chunks_per_batch(self) -> int:
        return 2048

    @override
    def _max_tokens_per_batch(self) -> int:
        return 600_000

    async def call_embed_api(self, documents: list[Document]) -> EmbeddingResponse:
        response = await self._embedder.create(
            input=cast(list[str] | Iterable[Iterable[int]], documents),
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
    def _batcher(self) -> BatchApiCaller[Document]:
        return BatchApiCaller(
            self._max_chunks_per_batch(),
            self._max_tokens_per_batch(),
            self.call_embed_api,
        )

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
        is_tokenized = self._encoder is not None
        try:
            return await self._batcher.batch_chunks_and_embed(
                encoded_documents, is_tokenized
            )
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

            # non-tokenized documents are discarded
            if self._encoder is None:
                raise e

            model_token_length = int(m.group(1))
            return await self._filter_by_length_and_embed(
                model_token_length, encoded_documents
            )

    async def _filter_by_length_and_embed(
        self, model_token_length: int, encoded_documents: list[Document]
    ) -> Sequence[EmbeddingVector | ChunkEmbeddingError]:
        """
        Filters out documents that exceed the model's token limit and embeds
        the valid ones. Chunks that exceed the limit are replaced in the
        response with an ChunkEmbeddingError instead of an EmbeddingVector.

        Args:
            model_token_length (int): The token length limit for the model.
            encoded_documents (list[Document]): A list of encoded documents.
            if non-encoded documents are provided, those are discarded.

        Returns:
            Sequence[EmbeddingVector | ChunkEmbeddingError]: EmbeddingVector
            for the chunks that were successfully embedded, ChunkEmbeddingError
            for the chunks that exceeded the model's token limit.
        """
        valid_documents: list[Document] = []
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

    async def _encode(self, documents: list[StringDocument]) -> list[Document]:
        """
        Encodes a list of documents into a list of tokenized documents, using
        the corresponding encoder for the model.
        In case no encoder is found, the documents are returned as is (NOOP).

        Args:
            documents (list[str]): A list of text documents to be tokenized.

        Returns:
            list[Document]: A list of tokenized or non-tokenized documents.
        """
        encoder = self._encoder
        if encoder is None:
            return list[Document](documents)

        total_tokens = 0
        encoded_documents: list[Document] = []
        for document in documents:
            if self.model.endswith("001"):
                # See: https://github.com/openai/openai-python/issues/418#issuecomment-1525939500
                # replace newlines, which can negatively affect performance.
                document = document.replace("\n", " ")

            tokenized = encoder.encode_ordinary(document)
            total_tokens += len(tokenized)
            encoded_documents.append(tokenized)
        await logger.adebug(f"Total tokens in batch: {total_tokens}")
        return encoded_documents

    @cached_property
    def _encoder(self) -> tiktoken.Encoding | None:
        try:
            encoder = tiktoken.encoding_for_model(self.model)
        except KeyError:
            logger.warning(
                f"Tokenizer for the model {self.model} not found. "
                "Fallback to non-tokenized plain text"
            )
            return None
        return encoder

    @override
    async def create_async_batch(
        self,
        documents: list[DocumentWithID],
    ) -> AsyncBatch:
        # TODO: docs outdated
        """
        Creates a batch of embeddings using OpenAI's embeddings API as outlined in
        https://platform.openai.com/docs/guides/batch/batch-api?lang=python

        Args:
            documents (list[str]): A list of document chunks to be embedded.

        Returns:

        """
        with (
            io.BytesIO() as bytes_stream,
            io.TextIOWrapper(bytes_stream, encoding="utf-8", newline="") as writer,
        ):
            for document in documents:
                entry = {
                    "custom_id": document.id,
                    "method": "POST",
                    "url": "/v1/embeddings",
                    "body": {"model": self.model, "input": document.content},
                }
                writer.write(json.dumps(entry) + "\n")
            writer.flush()

            bytes_stream.seek(0)
            batch_input_file = await self._client.files.create(
                file=bytes_stream,
                purpose="batch",
            )

        openai_batch = await self._client.batches.create(
            input_file_id=batch_input_file.id,
            endpoint="/v1/embeddings",
            completion_window="24h",
        )

        return openai_batch_to_async_batch(openai_batch, "pending")

    @override
    async def fetch_async_batch(self, batch_id: str) -> AsyncBatch:
        openai_batch = await self._client.batches.retrieve(batch_id)

        status = ""
        # For expired batches we can still fetch embeddings for the requests in
        # the file that were processed. Expired requests will be found in the
        # error file.
        if openai_batch.status in ["completed", "expired"]:
            status = "ready"
        elif openai_batch.status in ["validating", "in_progress", "finalizing"]:
            status = "pending"
        elif openai_batch.status in ["failed", "canceled", "cancelling"]:
            status = "failed"

        return openai_batch_to_async_batch(openai_batch, status)

    @override
    async def fetch_async_batch_embeddings(
        self,
        batch: AsyncBatch,
    ) -> list[tuple[str, EmbeddingVector]]:
        if "output_file_id" not in batch.metadata:  # type: ignore
            raise ValueError("output_file_id not found in async batch metadata")
        embedding_responses = await self._client.files.content(
            batch.metadata["output_file_id"]
        )

        embeddings: list[tuple[str, EmbeddingVector]] = []

        for line in embedding_responses.text.strip().split("\n"):
            json_line = json.loads(line)
            if not ("custom_id" in json_line and "response" in json_line):
                # TODO: should we skip and store the embeddings we got? Is this
                # scenario possible?
                raise ValueError("custom_id or response not found in response")
            custom_id: str = json_line["custom_id"]
            embedding_data: EmbeddingVector = json_line["response"]["body"]["data"][0][
                "embedding"
            ]

            embeddings.append((custom_id, embedding_data))

        # TODO: fetch and return errors
        # TODO: would it be better to return an interator so that we don't have
        # to load all the objects in memory? We are parsing line by line, so we
        # could return iterators and insert in batches into the DB.
        return embeddings

    @override
    async def finalize_async_batch(
        self,
        batch: AsyncBatch,
    ):
        await self._client.files.delete(batch.metadata["input_file_id"])

        output_file_id = batch.metadata["output_file_id"]
        if output_file_id is not None:
            await self._client.files.delete(batch.metadata["output_file_id"])

        error_file_id = batch.metadata["error_file_id"]
        if error_file_id is not None:
            await self._client.files.delete(batch.metadata["error_file_id"])

    @override
    def is_async_batch_enabled(self) -> bool:
        return self.async_batch_enabled


def openai_batch_to_async_batch(openai_batch: Batch, status: str) -> AsyncBatch:
    return AsyncBatch(
        id=openai_batch.id, status=status, metadata=openai_batch.to_dict()
    )
