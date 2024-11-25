import voyageai
from typing import Optional, Generator, Union

DEFAULT_KEY_NAME = "VOYAGE_API_KEY"


def embed(
    model: str,
    input: Union[list[str]],
    api_key: str,
    input_type: Optional[str] = None,
    truncation: Optional[bool] = None,
) -> Generator[tuple[int, list[float]], None, None]:
    client = voyageai.Client(api_key=api_key)
    args = {}
    if truncation is not None:
        args["truncation"] = truncation
    response = client.embed(input, model=model, input_type=input_type, **args)
    if not hasattr(response, "embeddings"):
        return None
    for idx, obj in enumerate(response.embeddings):
        yield idx, obj
