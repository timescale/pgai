import openai
from datetime import datetime
from typing import Optional, Generator, Union

DEFAULT_KEY_NAME = "OPENAI_API_KEY"


def get_openai_base_url(plpy) -> Optional[str]:
    r = plpy.execute(
        "select pg_catalog.current_setting('ai.openai_base_url', true) as base_url"
    )
    if len(r) == 0:
        return None
    return r[0]["base_url"]


def make_client(
    plpy,
    api_key: str,
    base_url: Optional[str] = None,
) -> openai.Client:
    if base_url is None:
        base_url = get_openai_base_url(plpy)
    return openai.Client(api_key=api_key, base_url=base_url)


def list_models(
    plpy,
    api_key: str,
    base_url: Optional[str] = None,
) -> Generator[tuple[str, datetime, str], None, None]:
    client = make_client(plpy, api_key, base_url)
    from datetime import datetime, timezone

    for model in client.models.list():
        created = datetime.fromtimestamp(model.created, timezone.utc)
        yield model.id, created, model.owned_by


def embed(
    plpy,
    model: str,
    input: Union[str, list[str], list[int]],
    api_key: str,
    base_url: Optional[str] = None,
    dimensions: Optional[int] = None,
    user: Optional[str] = None,
) -> Generator[tuple[int, list[float]], None, None]:
    client = make_client(plpy, api_key, base_url)
    args = {}
    if dimensions is not None:
        args["dimensions"] = dimensions
    if user is not None:
        args["user"] = user
    response = client.embeddings.create(input=input, model=model, **args)
    if not hasattr(response, "data"):
        return None
    for obj in response.data:
        yield obj.index, obj.embedding
