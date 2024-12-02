import math
import os
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import (
    Any,
    Generic,
    Literal,
    TypeAlias,
    TypeVar,
)

import ollama
import openai
import structlog
import tiktoken
from ddtrace import tracer
from openai import resources
from pydantic import BaseModel
from typing_extensions import TypedDict, override

MAX_RETRIES = 3

TOKEN_CONTEXT_LENGTH_ERROR = "chunk exceeds model context length"

openai_token_length_regex = re.compile(
    r"This model's maximum context length is (\d+) tokens"
)

logger = structlog.get_logger()


@dataclass
class ChunkEmbeddingError:
    """
    A data class to represent an error that occurs during chunk embedding.

    Attributes:
        error (str): A brief description of the error.
        error_details (str): Detailed information about the error.
    """

    error: str = ""
    error_details: str = ""


EmbeddingVector: TypeAlias = list[float]

StringDocument: TypeAlias = str
TokenDocument: TypeAlias = list[int]
Document: TypeAlias = StringDocument | TokenDocument


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


T = TypeVar("T", StringDocument, TokenDocument)


@dataclass
class BatchApiCaller(Generic[T]):
    max_chunks_per_batch: int
    api_callable: Callable[[list[T]], Awaitable[EmbeddingResponse]]

    async def batch_chunks_and_embed(self, documents: list[T]) -> list[EmbeddingVector]:
        """
        Performs the actual embedding of encoded documents by sending requests
        to the embedding API.

        Args:
            documents (list[T]): A list of documents.

        Returns:
            list[EmbeddingVector]: A list of embedding vectors for each document.
        """
        response: list[list[float]] = []
        max_chunks_per_batch = self.max_chunks_per_batch
        num_of_batches = math.ceil(len(documents) / max_chunks_per_batch)
        total_duration = 0.0
        embedding_stats = EmbeddingStats()
        with tracer.trace("embeddings.do"):
            current_span = tracer.current_span()
            if current_span:
                current_span.set_tag("batches.total", num_of_batches)
            for i in range(0, len(documents), max_chunks_per_batch):
                batch_num = i // max_chunks_per_batch + 1
                batch = documents[i : i + max_chunks_per_batch]

                await logger.adebug(f"Batch {batch_num} of {num_of_batches}")
                await logger.adebug(f"Chunks for this batch: {len(batch)}")
                await logger.adebug(
                    f"Request {batch_num} of {num_of_batches} initiated"
                )
                with tracer.trace("embeddings.do.embedder.create"):
                    current_span = tracer.current_span()
                    if current_span:
                        current_span.set_tag("batch.id", batch_num)
                        current_span.set_tag("batch.chunks.total", len(batch))
                    start_time = time.perf_counter()
                    response_ = await self.api_callable(batch)
                    request_duration = time.perf_counter() - start_time
                    if current_span:
                        current_span.set_metric(
                            "embeddings.embedder.create_request.time.seconds",
                            request_duration,
                        )

                    await logger.adebug(
                        f"Request {batch_num} of {num_of_batches} "
                        f"ended after: {request_duration} seconds. "
                        f"Tokens usage: {response_.usage}"
                    )
                    total_duration += request_duration

                    response += response_.embeddings

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

            return response


class Embedder(ABC):
    """
    Abstract base class for an Embedder.

    This class defines the interface for embedding text documents into vectors
    or returning embedding errors.
    """

    @abstractmethod
    async def embed(
        self, documents: list[str]
    ) -> Sequence[EmbeddingVector | ChunkEmbeddingError]:
        """
        Embeds a list of documents into vectors.

        Args:
            documents (list[str]): A list of strings representing the documents
            to be embedded.

        Returns:
            Sequence[EmbeddingVector | ChunkEmbeddingError]: A sequence of
            embedding vectors or errors encountered during embedding.
        """

    @abstractmethod
    def _max_chunks_per_batch(self) -> int:
        """
        The maximum number of chunks that can be embedded per API call
        :return: int: the max chunk count
        """


class ApiKeyMixin:
    """
    A mixin class that provides functionality for managing API keys.

    Attributes:
        api_key_name (str): The name of the API key attribute.
    """

    api_key_name: str
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

        api_key = secrets.get(self.api_key_name, None)
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
        return openai.AsyncOpenAI(
            api_key=self._api_key, max_retries=MAX_RETRIES
        ).embeddings

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


# Note: this is a re-declaration of ollama.Options, which we are forced to do
# otherwise pydantic complains (ollama.Options subclasses typing.TypedDict):
# pydantic.errors.PydanticUserError: Please use `typing_extensions.TypedDict` instead of `typing.TypedDict` on Python < 3.12. # noqa
class OllamaOptions(TypedDict, total=False):
    # load time options
    numa: bool
    num_ctx: int
    num_batch: int
    num_gpu: int
    main_gpu: int
    low_vram: bool
    f16_kv: bool
    logits_all: bool
    vocab_only: bool
    use_mmap: bool
    use_mlock: bool
    embedding_only: bool
    num_thread: int

    # runtime options
    num_keep: int
    seed: int
    num_predict: int
    top_k: int
    top_p: float
    tfs_z: float
    typical_p: float
    repeat_last_n: int
    temperature: float
    repeat_penalty: float
    presence_penalty: float
    frequency_penalty: float
    mirostat: int
    mirostat_tau: float
    mirostat_eta: float
    penalize_newline: bool
    stop: Sequence[str]


class Ollama(BaseModel, Embedder):
    """
    Embedder that uses Ollama to embed documents into vector representations.

    Attributes:
        implementation (Literal["ollama"]): The literal identifier for this
            implementation.
        model (str): The name of the Ollama model used for embeddings.
        base_url (str): The base url used to access the Ollama API.
        truncate (bool): Truncate input longer than the model's context length
        options (dict): Additional ollama-specific runtime options
        keep_alive (str): How long to keep the model loaded after the request
    """

    implementation: Literal["ollama"]
    model: str
    base_url: str | None = None
    truncate: bool = True
    options: OllamaOptions | None = None
    keep_alive: str | None = None  # this is only `str` because of the SQL API

    @override
    async def embed(
        self, documents: list[str]
    ) -> Sequence[EmbeddingVector | ChunkEmbeddingError]:
        """
        Embeds a list of documents into vectors using Ollama's embeddings API.

        If a request to generate embeddings fails because one or more chunks
        exceed the model's token limit (and truncate is set to False), every
        chunk will be retried individually. The returned result will contain a
        ChunkEmbeddingError in place of an EmbeddingVector for the chunks that
        exceeded the model's token limit.

        Args:
            documents (list[str]): A list of documents to be embedded.

        Returns:
            Sequence[EmbeddingVector | ChunkEmbeddingError]: The embeddings or
            errors for each document.
        """
        await logger.adebug(f"Chunks produced: {len(documents)}")
        try:
            return await self._batcher.batch_chunks_and_embed(documents)
        except ollama.ResponseError as e:
            if "input length exceeds maximum context length" not in e.error:
                raise e
            # Note: We don't attempt tokenizing data sent to Ollama models
            # because every model has its own tokenizer, and there's no way to
            # programmatically determine the tokenizer. Without knowing the
            # token length of a chunk, we can't filter the long ones out (like
            # we do in the OpenAI integration). Instead, we retry each chunk
            # individually. It's not ideal, but not too bad because it's
            # (probably) a local API.
            context_length = await self._context_length()
            return await self._fallback_retry_individually(context_length, documents)

    @cached_property
    def _batcher(self) -> BatchApiCaller[StringDocument]:
        return BatchApiCaller(self._max_chunks_per_batch(), self.call_embed_api)

    @override
    def _max_chunks_per_batch(self) -> int:
        # Note: the chosen default is arbitrary - Ollama doesn't place a limit
        return int(
            os.getenv("PGAI_VECTORIZER_OLLAMA_MAX_CHUNKS_PER_BATCH", default="2048")
        )

    async def call_embed_api(self, documents: str | list[str]) -> EmbeddingResponse:
        response = await ollama.AsyncClient(host=self.base_url).embed(
            model=self.model,
            input=documents,
            truncate=self.truncate,
            options=self.options,
            keep_alive=self.keep_alive,
        )
        usage = Usage(
            prompt_tokens=response["prompt_eval_count"],
            total_tokens=response["prompt_eval_count"],
        )
        return EmbeddingResponse(embeddings=response["embeddings"], usage=usage)

    async def _model(self) -> Mapping[str, Any]:
        """
        Gets the model details from the Ollama API
        :return:
        """
        return await ollama.AsyncClient(host=self.base_url).show(self.model)

    async def _context_length(self) -> int | None:
        """
        Gets the context_length of the configured model, if available
        """
        model = await self._model()
        architecture = model["model_info"].get("general.architecture", None)
        if architecture is None:
            logger.warn(f"unable to determine architecture for model '{self.model}'")
            return None
        context_key = f"{architecture}.context_length"
        # see https://github.com/ollama/ollama/blob/712d63c3f06f297e22b1ae32678349187dccd2e4/llm/ggml.go#L116-L118 # noqa
        model_context_length = model["model_info"][context_key]
        # the context window can be configured, so pull the value from the config
        num_ctx = (
            float("inf")
            if self.options is None
            else self.options.get("num_ctx", float("inf"))
        )
        return min(model_context_length, num_ctx)

    async def _fallback_retry_individually(
        self, model_token_length: int | None, documents: list[str]
    ) -> Sequence[EmbeddingVector | ChunkEmbeddingError]:
        """
        Retries embedding all documents individually. Chunks that fail are
        converted to a ChunkEmbeddingError instead of an EmbeddingVector.

        Args:
            model_token_length (int | None): The token length limit for the model.
            documents (list[str]): A list of documents.

        Returns:
            Sequence[EmbeddingVector | ChunkEmbeddingError]: EmbeddingVector
            for the chunks that were successfully embedded, ChunkEmbeddingError
            for the chunks that exceeded the model's token limit.
        """
        embeddings: list[ChunkEmbeddingError | list[float]] = []
        for doc in documents:
            try:
                response = await self._batcher.batch_chunks_and_embed([doc])
                embeddings.append(response[0])
            except ollama.ResponseError as e:
                if "input length exceeds maximum context length" in e.error:
                    error_details = (
                        f"chunk exceeds the {self.model} model context length"
                    )
                    if model_token_length is not None:
                        error_details += f"of {model_token_length} tokens"
                    error = ChunkEmbeddingError(
                        error=TOKEN_CONTEXT_LENGTH_ERROR, error_details=error_details
                    )
                    embeddings.append(error)
                else:
                    embeddings.append(
                        ChunkEmbeddingError(
                            error="unknown error",
                            error_details=f"unexpected error: '{e}'",  # noqa
                        )
                    )
        return embeddings
