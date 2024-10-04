import math
import re
import time
from abc import ABC, abstractmethod
from functools import cached_property
from typing import Literal, Optional, Sequence, Union, TypeAlias

import openai
import structlog
import tiktoken
from ddtrace import tracer
from openai import resources
from pydantic import BaseModel
from pydantic.dataclasses import dataclass

from .secrets import Secrets

MAX_RETRIES = 3

TOKEN_CONTEXT_LENGTH_ERROR = "chunk exceeds model context length"
OPENAI_MAX_CHUNKS_PER_BATCH = 2048

openai_token_length_regex = re.compile(
    r"This model's maximum context length is (\d+) tokens"
)

logger = structlog.get_logger()


@dataclass
class ChunkEmbeddingError:
    error: str = ""
    error_details: str = ""


EmbeddingVector: TypeAlias = list[float]


class Embedder(ABC):
    @abstractmethod
    async def embed(
        self, documents: list[str]
    ) -> Sequence[Union[EmbeddingVector, ChunkEmbeddingError]]:
        pass


class ApiKeyMixin:
    api_key_name: str
    _api_key_: Optional[str] = None

    @property
    def _api_key(self) -> str:
        if self._api_key_ is None:
            raise ValueError("API key not set")
        return self._api_key_

    def set_api_key(self, secrets: Secrets):
        api_key = getattr(secrets, self.api_key_name)
        if api_key is None:
            raise ValueError(f"missing API key: {self.api_key_name}")
        self._api_key_ = api_key


class EmbeddingStats:
    total_request_time: float
    total_chunks: int
    wall_time: float
    wall_start: float

    def __new__(cls):
        if not hasattr(cls, '_instance'):
            cls._instance = super().__new__(cls)
            
            cls._instance.total_request_time = 0.0
            cls._instance.total_chunks = 0
            cls._instance.wall_time = 0
            cls._instance.wall_start = time.perf_counter()
        return cls._instance

    def add_request_time(self, duration: float, chunk_count: int):
        self.total_request_time += duration
        self.total_chunks += chunk_count

    async def print_stats(self):
        chunks_per_second = self.total_chunks / self.total_request_time if self.total_request_time > 0 else 0
        self.wall_time = time.perf_counter() - self.wall_start
        await logger.adebug(
            "Embedding stats",
            total_request_time = self.total_request_time,
            wall_time = self.wall_time,
            total_chunks = self.total_chunks,
            chunks_per_second = chunks_per_second
        )


class OpenAI(ApiKeyMixin, BaseModel, Embedder):
    implementation: Literal["openai"]
    model: str
    dimensions: Optional[int] = None
    user: Optional[str] = None

    @cached_property
    def _openai_dimensions(self) -> Union[int, openai.NotGiven]:
        return self.dimensions if self.dimensions is not None else openai.NOT_GIVEN

    @cached_property
    def _openai_user(self) -> Union[str, openai.NotGiven]:
        return self.user if self.user is not None else openai.NOT_GIVEN

    @cached_property
    def _embedder(self) -> resources.AsyncEmbeddings:
        return openai.AsyncOpenAI(
            api_key=self._api_key, max_retries=MAX_RETRIES
        ).embeddings

    async def embed(
        self, documents: list[str]
    ) -> Sequence[Union[EmbeddingVector, ChunkEmbeddingError]]:
        encoded_documents = await self._encode(documents)
        await logger.adebug(f"Chunks produced: {len(documents)}")
        try:
            return await self._do_embed(encoded_documents)
        except openai.BadRequestError as e:
            if (
                e.body is None
                or not isinstance(e.body, dict)
                or "message" not in e.body
            ):
                raise e

            m = openai_token_length_regex.match(e.body["message"])
            if not m:
                raise e
            model_token_length = int(m.group(1))
            return await self._filter_by_length_and_embed(
                model_token_length, encoded_documents
            )

    async def _do_embed(
        self, encoded_documents: list[list[int]]
    ) -> list[EmbeddingVector]:
        response = []
        num_of_batches = math.ceil(len(encoded_documents) / OPENAI_MAX_CHUNKS_PER_BATCH)
        total_duration = 0.0
        embedding_stats = EmbeddingStats()
        with tracer.trace("embeddings.do"):
            current_span = tracer.current_span()
            if current_span: 
                current_span.set_tag('batches.total', num_of_batches)
            for i in range(0, len(encoded_documents), OPENAI_MAX_CHUNKS_PER_BATCH):
                batch_num = i // OPENAI_MAX_CHUNKS_PER_BATCH + 1
                batch = encoded_documents[i : i + OPENAI_MAX_CHUNKS_PER_BATCH]

                await logger.adebug(f"Batch {batch_num} of {num_of_batches}")
                await logger.adebug(f"Chunks for this batch: {len(batch)}")
                await logger.adebug(
                    f"OpenAI Request {batch_num} of {num_of_batches} initiated"
                )
                with tracer.trace("embeddings.do.embedder.create"):
                    current_span = tracer.current_span()
                    if current_span:
                        current_span.set_tag("batch.id", batch_num)
                        current_span.set_tag("batch.chunks.total", len(batch))
                    start_time = time.perf_counter()
                    response_ = await self._embedder.create(
                        input=batch,
                        model=self.model,
                        dimensions=self._openai_dimensions,
                        user=self._openai_user,
                        encoding_format="float",
                    )
                    request_duration = time.perf_counter() - start_time
                    if current_span: 
                        current_span.set_metric("embeddings.embedder.create_request.time.seconds", request_duration)
                        
                    await logger.adebug(
                        f"OpenAI Request {batch_num} of {num_of_batches} ended after: {request_duration} seconds. Tokens usage: {response_.usage}"
                    )
                    total_duration += request_duration
                    
                    response += [r.embedding for r in response_.data]
            
            embedding_stats.add_request_time(total_duration, len(encoded_documents))
            await embedding_stats.print_stats()
            if current_span: 
                current_span.set_metric('embeddings.embedder.all_create_requests.time.seconds', embedding_stats.total_request_time)
                current_span.set_metric('embeddings.embedder.all_create_requests.wall_time.seconds', embedding_stats.wall_time)
            
            return response

    async def _filter_by_length_and_embed(
        self, model_token_length: int, encoded_documents: list[list[int]]
    ) -> Sequence[Union[EmbeddingVector, ChunkEmbeddingError]]:
        valid_documents = []
        invalid_documents_idxs = []
        for i, doc in enumerate(encoded_documents):
            if len(doc) > model_token_length:
                invalid_documents_idxs.append(i)
            else:
                valid_documents.append(doc)

        assert len(valid_documents) + len(invalid_documents_idxs) == len(
            encoded_documents
        )

        response = await self._embedder.create(
            input=valid_documents,
            model=self.model,
            dimensions=self._openai_dimensions,
            encoding_format="float",
        )

        embeddings = []
        for i in range(len(encoded_documents)):
            if i in invalid_documents_idxs:
                embedding = ChunkEmbeddingError(
                    error=TOKEN_CONTEXT_LENGTH_ERROR,
                    error_details=f"chunk exceeds the {self.model} model context length of {model_token_length} tokens",
                )
            else:
                embedding = response.data.pop(0).embedding
            embeddings.append(embedding)

        return embeddings

    async def _encode(self, documents: list[str]) -> list[list[int]]:
        total_tokens = 0
        encoded_documents = []
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
