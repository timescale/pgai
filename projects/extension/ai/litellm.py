import litellm
from typing import Optional, Generator


def embed(
    model: str,
    input: list[str],
    api_key: str,
    user: Optional[str] = None,
    dimensions: Optional[int] = None,
    timeout: Optional[int] = None,
    api_base: Optional[str] = None,
    api_version: Optional[str] = None,
    api_type: Optional[str] = None,
    organization: Optional[str] = None,
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
