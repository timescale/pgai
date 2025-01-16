from collections.abc import Generator

import voyageai

DEFAULT_KEY_NAME = "VOYAGE_API_KEY"


def embed(
    model: str,
    input: list[str],
    api_key: str,
    input_type: str | None = None,
    truncation: bool | None = None,
) -> Generator[tuple[int, list[float]], None, None]:
    client = voyageai.Client(api_key=api_key)
    args = {}
    if truncation is not None:
        args["truncation"] = truncation
    response = client.embed(input, model=model, input_type=input_type, **args)
    if not hasattr(response, "embeddings"):
        return None
    yield from enumerate(response.embeddings)
