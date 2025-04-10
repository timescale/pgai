from collections.abc import AsyncGenerator
from typing import Any, Literal

from pydantic import BaseModel
from typing_extensions import override

from ..embeddings import (
    ApiKeyMixin,
    Embedder,
    EmbeddingResponse,
    EmbeddingVector,
    Usage,
    logger,
)


class LiteLLM(ApiKeyMixin, BaseModel, Embedder):
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
    extra_options: dict[str, Any] = {}

    @override
    async def embed(
        self, documents: list[str]
    ) -> AsyncGenerator[list[EmbeddingVector], None]:
        """
        Embeds a list of documents into vectors using LiteLLM.

        Args:
            documents (list[str]): A list of documents to be embedded.

        Returns:
            Sequence[EmbeddingVector]: The embeddings for each document.
        """
        await logger.adebug(f"Chunks produced: {len(documents)}")
        chunk_lengths = [0 for _ in documents]
        async for embeddings in self.batch_chunks_and_embed(documents, chunk_lengths):
            yield embeddings

    @override
    def _max_chunks_per_batch(self) -> int:
        # Note: deferred import to avoid import overhead
        import litellm

        _, custom_llm_provider, _, _ = litellm.get_llm_provider(self.model)  # type: ignore
        match custom_llm_provider:
            case "cohere":
                return 96  # see https://docs.cohere.com/v1/reference/embed#request.body.texts
            case "openai":
                return 2048  # see https://platform.openai.com/docs/api-reference/embeddings/create
            case "azure":
                return 2048  # https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/embeddings?tabs=console#verify-inputs-dont-exceed-the-maximum-length
            case "bedrock":
                return 96  # NOTE: currently (Jan 2025) Bedrock only supports embeddings with Cohere or Titan models. The Titan API only processes one input per request, which LiteLLM already handles under the hood. We assume that the Cohere API has the same input limits as above.  # noqa
            case "huggingface":
                return 2048  # NOTE: There is not documented limit. In testing we got a response for a request with 10k (short) inputs.  # noqa
            case "mistral":
                return 128  # FIXME: this is chosen somewhat arbitrarily. There is no limit on # chunks per batch, but there is a (low) limit on # tokens per batch (16384)  # noqa
            case "vertex_ai":
                return 250  # FIXME: this applies to `us-central-1` only (otherwise 5). Additionally there is a limit on # tokens per batch (20k) see https://cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-text-embeddings#get_text_embeddings_for_a_snippet_of_text  # noqa
            case "voyage":
                return 128  # see https://docs.voyageai.com/reference/embeddings-api
            case _:
                logger.warn(
                    f"unknown provider '{custom_llm_provider}', falling back to conservative max chunks per batch"  # noqa: E501
                )
                return 5

    @override
    async def call_embed_api(self, documents: list[str]) -> EmbeddingResponse:
        # Note: deferred import to avoid import overhead
        import litellm

        # Without `suppress_debug_info`, LiteLLM writes the following into stdout:
        # Provider List: https://docs.litellm.ai/docs/providers
        # This is useless, and confusing, so we suppress it.
        litellm.suppress_debug_info = True
        api_key = None if self.api_key_name is None else self._api_key
        response = await litellm.aembedding(  # type: ignore
            model=self.model,
            input=documents,
            api_key=api_key,
            **self.extra_options,
        )
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
