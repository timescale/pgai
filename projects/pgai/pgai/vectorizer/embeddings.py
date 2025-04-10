import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TypeAlias

import structlog
from ddtrace import tracer

logger = structlog.get_logger()

EmbeddingVector: TypeAlias = list[float]


@dataclass
class Usage:
    """The number of tokens used in an embedding request"""

    prompt_tokens: int
    total_tokens: int


@dataclass
class EmbeddingResponse:
    """A generic embedding response"""

    embeddings: list[list[float]]
    usage: Usage


class BatchingError(BaseException):
    pass


def batch_indices(
    chunk_token_lengths: list[int],
    max_chunks_per_batch: int,
    max_tokens_per_batch: int | None,
) -> list[tuple[int, int]]:
    """
    Given a list of chunk token lengths, determines how to batch them, adhering to
    configured 'max_chunks_per_batch' and 'max_tokens_per_batch'.

    Returns a list of tuples indicating the chunk indexes to include in the batch
    """
    batches: list[list[int]] = []
    batch: list[int] = []
    token_count = 0
    for idx, chunk_tokens in enumerate(chunk_token_lengths):
        if max_tokens_per_batch is not None and chunk_tokens > max_tokens_per_batch:
            raise BatchingError(
                f"chunk length {chunk_tokens} greater than max_tokens_per_batch {max_tokens_per_batch}"  # noqa
            )
        max_tokens_reached = (
            max_tokens_per_batch is not None
            and token_count + chunk_tokens > max_tokens_per_batch
        )
        max_chunks_reached = len(batch) + 1 > max_chunks_per_batch
        if max_tokens_reached or max_chunks_reached:
            logger.debug(
                f"Batch {len(batches) + 1} has {token_count} tokens in {len(batch)} chunks"  # noqa
            )
            batches.append(batch)
            batch = []
            token_count = 0
        batch.append(idx)
        token_count += chunk_tokens
    if batch:
        logger.debug(
            f"Batch {len(batches) + 1} has {token_count} tokens in {len(batch)} chunks"
        )
        batches.append(batch)
    return [(idxs[0], idxs[-1] + 1) for idxs in batches]


class Embedder(ABC):
    """
    Abstract base class for an Embedder.

    This class defines the interface for embedding text documents into vectors
    or returning embedding errors.
    """

    @abstractmethod
    async def embed(
        self, documents: list[str]
    ) -> AsyncGenerator[list[EmbeddingVector], None]:
        """
        Embeds a list of documents into vectors.

        Args:
            documents (list[str]): A list of strings representing the documents
            to be embedded.

        Returns:
            AsyncGenerator[list[EmbeddingVector], None]: A sequence of
            embedding vectors.
        """
        raise NotImplementedError
        yield ""  # https://github.com/microsoft/pyright/issues/9949

    @abstractmethod
    def _max_chunks_per_batch(self) -> int:
        """
        The maximum number of chunks that can be embedded per API call
        :return: int: the max chunk count
        """

    def _max_tokens_per_batch(self) -> int | None:
        """
        The maximum number of tokens that can be embedded per API call
        :return: int: the max token count
        """
        return None

    async def setup(self) -> None:  # noqa: B027 empty on purpose
        """
        Setup the embedder
        """

    @abstractmethod
    async def call_embed_api(self, documents: list[str]) -> EmbeddingResponse:
        """
        Call the embed API
        :param documents:
        :return:
        """

    async def batch_chunks_and_embed(
        self, documents: list[str], token_counts: list[int]
    ) -> AsyncGenerator[list[EmbeddingVector], None]:
        """
        Performs the actual embedding of encoded documents by sending requests
        to the embedding API.

        Args:
            documents (list[str]): A list of documents.
            token_counts (list[int]): A list of token count for each document, or 0
        Returns:
            AsyncGenerator[list[EmbeddingVector], None]: A list of embedding vectors
            for each document.
        """
        assert len(documents) == len(token_counts)
        max_chunks_per_batch = self._max_chunks_per_batch()
        max_tokens_per_batch = self._max_tokens_per_batch()
        batches = batch_indices(
            token_counts,
            max_chunks_per_batch=max_chunks_per_batch,
            max_tokens_per_batch=max_tokens_per_batch,
        )
        num_batches = len(batches)

        total_duration = 0.0
        embedding_stats = EmbeddingStats()
        with tracer.trace("embeddings.do"):
            current_span = tracer.current_span()
            if current_span:
                current_span.set_tag("batches.total", num_batches)
                current_span.set_tag("tokens.total", sum(token_counts))
            for i, (start, end) in enumerate(batches):
                batch_num = i + 1
                batch = documents[start:end]

                await logger.adebug(f"Batch {batch_num} of {num_batches}")
                await logger.adebug(f"Chunks for this batch: {len(batch)}")
                await logger.adebug(f"Request {batch_num} of {num_batches} initiated")
                with tracer.trace("embeddings.do.embedder.create"):
                    current_span = tracer.current_span()
                    if current_span:
                        current_span.set_tag("batch.id", batch_num)
                        current_span.set_tag("batch.chunks.total", len(batch))
                        current_span.set_tag(
                            "batch.tokens.total", sum(token_counts[start:end])
                        )
                    start_time = time.perf_counter()
                    response_ = await self.call_embed_api(batch)
                    request_duration = time.perf_counter() - start_time
                    if current_span:
                        current_span.set_metric(
                            "embeddings.embedder.create_request.time.seconds",
                            request_duration,
                        )

                    await logger.adebug(
                        f"Request {batch_num} of {num_batches} "
                        f"ended after: {request_duration} seconds. "
                        f"Tokens usage: {response_.usage}"
                    )
                    total_duration += request_duration

                    yield response_.embeddings

            embedding_stats.add_request_time(total_duration, len(documents))
            await embedding_stats.print_stats()
            current_span = tracer.current_span()
            if current_span:
                current_span.set_metric(
                    "embeddings.embedder.all_create_requests.time.seconds",
                    embedding_stats.total_request_time,
                )
                current_span.set_metric(
                    "embeddings.embedder.all_create_requests.wall_time.seconds",
                    embedding_stats.wall_time,
                )
                current_span.set_metric(
                    "embeddings.embedder.all_create_requests.chunks.rate",
                    embedding_stats.chunks_per_second(),
                )


class BaseURLMixin:
    """
    A mixin class that provides functionality for managing base URLs.

    Attributes:
        base_url (str | None): The base URL for the API.
    """

    base_url: str | None = None


class ApiKeyMixin:
    """
    A mixin class that provides functionality for managing API keys.

    Attributes:
        api_key_name (str): The name of the API key attribute.
    """

    api_key_name: str | None = None
    _api_key_: str | None = None

    @property
    def _api_key(self) -> str:
        """
        Retrieves the stored API key.

        Raises:
            ValueError: If the API key has not been set.

        Returns:
            str: The API key.
        """
        if self._api_key_ is None:
            raise ValueError("API key not set")
        return self._api_key_

    def set_api_key(self, secrets: dict[str, str | None]):
        """
        Sets the API key from the provided secrets.

        Args:
            secrets (Any): An object containing the API key as an attribute.

        Raises:
            ValueError: If the API key is missing from the secrets.
        """

        api_key = (
            secrets.get(self.api_key_name, None)
            if self.api_key_name is not None
            else None
        )
        if api_key is None:
            raise ValueError(f"missing API key: {self.api_key_name}")
        self._api_key_ = api_key


class EmbeddingStats:
    """
    Singleton class that tracks embedding statistics.

    This class measures total request time, total chunks processed, and
    calculates the number of chunks processed per second.

    Attributes:
        total_request_time (float): The total time spent on embedding requests.
        total_chunks (int): The total number of chunks processed.
        wall_time (float): The total elapsed time since the start of tracking.
        wall_start (float): The time at which tracking started.
    """

    total_request_time: float
    total_chunks: int
    wall_time: float
    wall_start: float

    def __new__(cls):
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)

            cls._instance.total_request_time = 0.0
            cls._instance.total_chunks = 0
            cls._instance.wall_time = 0
            cls._instance.wall_start = time.perf_counter()
        return cls._instance

    def add_request_time(self, duration: float, chunk_count: int):
        """
        Adds the duration of an embedding request and the number of chunks
        processed.

        Args:
            duration (float): The time taken for the request.
            chunk_count (int): The number of chunks processed in the request.
        """
        self.total_request_time += duration
        self.total_chunks += chunk_count

    def chunks_per_second(self):
        """
        Calculates the number of chunks processed per second.

        Returns:
            float: The number of chunks processed per second. Returns 0 if no
            requests have been processed.
        """
        return (
            self.total_chunks / self.total_request_time
            if self.total_request_time > 0
            else 0
        )

    async def print_stats(self):
        """
        Logs embedding statistics, including request time, total chunks, and
        chunks per second.
        """
        self.wall_time = time.perf_counter() - self.wall_start
        await logger.adebug(
            "Embedding stats",
            total_request_time=self.total_request_time,
            wall_time=self.wall_time,
            total_chunks=self.total_chunks,
            chunks_per_second=self.chunks_per_second(),
        )
