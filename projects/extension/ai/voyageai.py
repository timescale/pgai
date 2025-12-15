from collections.abc import Generator

import voyageai

DEFAULT_KEY_NAME = "VOYAGE_API_KEY"


def embed(
    model: str,
    input: list[str],
    api_key: str,
    input_type: str | None = None,
    truncation: bool | None = None,
    output_dimension: int | None = None,
    output_dtype: str | None = None,
) -> Generator[tuple[int, list[float]], None, None]:
    client = voyageai.Client(api_key=api_key)
    args = {}
    if truncation is not None:
        args["truncation"] = truncation
    if output_dimension is not None:
        args["output_dimension"] = output_dimension
    if output_dtype is not None:
        args["output_dtype"] = output_dtype
    response = client.embed(input, model=model, input_type=input_type, **args)
    if not hasattr(response, "embeddings"):
        return None
    yield from enumerate(response.embeddings)


def rerank(
    model: str,
    query: str,
    documents: list[str],
    api_key: str,
    top_k: int | None = None,
    truncation: bool | None = None,
) -> dict:
    """
    Rerank documents using Voyage AI reranker API.
    Returns the response as a dictionary for JSON serialization.
    """
    client = voyageai.Client(api_key=api_key)
    args = {}
    if top_k is not None:
        args["top_k"] = top_k
    if truncation is not None:
        args["truncation"] = truncation

    response = client.rerank(model=model, query=query, documents=documents, **args)

    # Convert response to dict for JSON serialization
    return {
        "results": [
            {
                "index": r.index,
                "document": r.document,
                "relevance_score": r.relevance_score,
            }
            for r in response.results
        ],
        "total_tokens": response.total_tokens,
    }
