from collections.abc import Sequence
from functools import cached_property
from typing import Any, Literal

import litellm
from litellm import EmbeddingResponse as LiteLLMEmbeddingResponse  # type: ignore
from pydantic import BaseModel
from typing_extensions import override

from ..embeddings import (
    BatchApiCaller,
    Embedder,
    EmbeddingResponse,
    EmbeddingVector,
    StringDocument,
    Usage,
    logger,
)


class UnknownProviderError(Exception):
    pass


class LiteLLM(BaseModel, Embedder):
    """
    Embedder that uses LiteLLM to embed documents into vector representations.

    Attributes:
        implementation (Literal["litellm"]): The literal identifier for this
            implementation.
        model (str): The name of the embedding model.
        api_key_name (str): The API key name.
        extra_options (dict): Additional litellm-specific options
    """

    implementation: Literal["litellm"]
    model: str
    api_key_name: str | None = None
    extra_options: dict[str, Any] = {}

    @override
    async def embed(self, documents: list[str]) -> Sequence[EmbeddingVector]:
        """
        Embeds a list of documents into vectors using LiteLLM.

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
        print(f"model: {self.model}")
        _, custom_llm_provider, _, _ = litellm.get_llm_provider(self.model)  # type: ignore
        match custom_llm_provider:
            case "cohere":
                return 96  # see https://docs.cohere.com/v1/reference/embed#request.body.texts
            case "openai":
                return 2048  # see https://platform.openai.com/docs/api-reference/embeddings/create
            case "azure":
                return 1024  # TODO: unknown
            case "bedrock":
                return 2048  # TODO: unknown
            case "huggingface":
                return 1024  # TODO: unknown
            case "mistral":
                return 1024  # TODO: unknown
            case "vertex":
                return 1024  # TODO: unknown
            case "voyage":
                return 128  # see https://docs.voyageai.com/reference/embeddings-api
            case _:
                raise UnknownProviderError(custom_llm_provider)

    async def call_embed_api(self, documents: str | list[str]) -> EmbeddingResponse:
        # Without `suppress_debug_info`, LiteLLM writes the following into stdout:
        # Provider List: https://docs.litellm.ai/docs/providers
        # This is useless, and confusing, so we suppress it.
        litellm.suppress_debug_info = True
        response: LiteLLMEmbeddingResponse = await litellm.aembedding(
            model=self.model, input=documents, **self.extra_options
        )  # type: ignore
        usage = (
            Usage(
                prompt_tokens=response.usage.prompt_tokens,
                total_tokens=response.usage.total_tokens,
            )
            if response.usage is not None
            else Usage(prompt_tokens=0, total_tokens=0)
        )
        return EmbeddingResponse(
            embeddings=[d["embedding"] for d in response["data"]], usage=usage
        )
