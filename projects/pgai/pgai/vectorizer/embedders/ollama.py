import os
from collections.abc import Sequence
from functools import cached_property
from typing import Literal

import ollama
from ollama import ShowResponse
from pydantic import BaseModel
from typing_extensions import TypedDict, override

from ..embeddings import (
    BatchApiCaller,
    Embedder,
    EmbeddingResponse,
    EmbeddingVector,
    StringDocument,
    Usage,
    logger,
)


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
        options (dict): Additional ollama-specific runtime options
        keep_alive (str): How long to keep the model loaded after the request
    """

    implementation: Literal["ollama"]
    model: str
    base_url: str | None = None
    options: OllamaOptions | None = None
    keep_alive: str | None = None  # this is only `str` because of the SQL API

    @override
    async def embed(self, documents: list[str]) -> Sequence[EmbeddingVector]:
        """
        Embeds a list of documents into vectors using Ollama's embeddings API.

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
        # Note: the chosen default is arbitrary - Ollama doesn't place a limit
        return int(
            os.getenv("PGAI_VECTORIZER_OLLAMA_MAX_CHUNKS_PER_BATCH", default="2048")
        )

    @override
    async def setup(self):
        client = ollama.AsyncClient(host=self.base_url)
        try:
            await client.show(self.model)
        except ollama.ResponseError as e:
            if f"model '{self.model}' not found" in e.error:
                logger.warn(
                    f"pulling ollama model '{self.model}', this may take a while"
                )
                await client.pull(self.model)

    async def call_embed_api(self, documents: str | list[str]) -> EmbeddingResponse:
        response = await ollama.AsyncClient(host=self.base_url).embed(
            model=self.model,
            input=documents,
            options=self.options,
            keep_alive=self.keep_alive,
        )
        usage = Usage(
            prompt_tokens=response["prompt_eval_count"],
            total_tokens=response["prompt_eval_count"],
        )
        return EmbeddingResponse(embeddings=response["embeddings"], usage=usage)

    async def _model(self) -> ShowResponse:
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
