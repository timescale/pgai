from collections.abc import Generator

import litellm


def embed(
    model: str,
    input: list[str],
    api_key: str,
    user: str | None = None,
    dimensions: int | None = None,
    timeout: int | None = None,
    api_base: str | None = None,
    api_version: str | None = None,
    api_type: str | None = None,
    organization: str | None = None,
    **kwargs,
) -> Generator[tuple[int, list[float]], None, None]:
    if organization is not None:
        litellm.organization = organization
    response = litellm.embedding(
        model=model,
        input=input,
        user=user,
        dimensions=dimensions,
        timeout=timeout,
        api_type=api_type,
        api_key=api_key,
        api_base=api_base,
        api_version=api_version,
        **kwargs,
    )
    if not hasattr(response, "data"):
        return None
    for idx, obj in enumerate(response["data"]):
        yield idx, obj["embedding"]
