import openai
from datetime import datetime
from typing import Optional, Generator, Union


def get_openai_api_key(plpy) -> str:
    r = plpy.execute(
        "select pg_catalog.current_setting('ai.openai_api_key', true) as api_key"
    )
    if len(r) == 0:
        plpy.error("missing api key")
    return r[0]["api_key"]


def make_client(plpy, api_key: Optional[str] = None) -> openai.Client:
    if api_key is None:
        api_key = get_openai_api_key(plpy)
    return openai.Client(api_key=api_key)


def list_models(
    plpy, api_key: Optional[str] = None
) -> Generator[tuple[str, datetime, str], None, None]:
    client = make_client(plpy, api_key)
    from datetime import datetime, timezone

    for model in client.models.list():
        created = datetime.fromtimestamp(model.created, timezone.utc)
        yield model.id, created, model.owned_by


def embed(
    plpy,
    model: str,
    input: Union[str, list[str], list[int]],
    api_key: Optional[str] = None,
    dimensions: Optional[int] = None,
    user: Optional[str] = None,
) -> Generator[tuple[int, list[float]], None, None]:
    client = make_client(plpy, api_key)
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
