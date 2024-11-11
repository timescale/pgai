import openai
from datetime import datetime
from typing import Optional, Generator, Union
from .secrets import reveal_secret


def get_openai_api_key(plpy, api_key_name: Optional[str] = None) -> str:
    if api_key_name is None:
        api_key_name = "OPENAI_API_KEY"
    key = reveal_secret(plpy, api_key_name)
    if key is None:
        plpy.error(f"missing {api_key_name} secret")
        # This line should never be reached, but it's here to make the type checker happy.
        return ""
    return key


def get_openai_base_url(plpy) -> Optional[str]:
    r = plpy.execute(
        "select pg_catalog.current_setting('ai.openai_base_url', true) as base_url"
    )
    if len(r) == 0:
        return None
    return r[0]["base_url"]


def make_client(
    plpy,
    api_key: Optional[str] = None,
    api_key_name: Optional[str] = None,
    base_url: Optional[str] = None,
) -> openai.Client:
    if api_key is None:
        api_key = get_openai_api_key(plpy, api_key_name)
    if base_url is None:
        base_url = get_openai_base_url(plpy)
    return openai.Client(api_key=api_key, base_url=base_url)


def list_models(
    plpy,
    api_key: Optional[str] = None,
    api_key_name: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Generator[tuple[str, datetime, str], None, None]:
    client = make_client(plpy, api_key, api_key_name, base_url)
    from datetime import datetime, timezone

    for model in client.models.list():
        created = datetime.fromtimestamp(model.created, timezone.utc)
        yield model.id, created, model.owned_by


def embed(
    plpy,
    model: str,
    input: Union[str, list[str], list[int]],
    api_key: Optional[str] = None,
    api_key_name: Optional[str] = None,
    base_url: Optional[str] = None,
    dimensions: Optional[int] = None,
    user: Optional[str] = None,
) -> Generator[tuple[int, list[float]], None, None]:
    client = make_client(plpy, api_key, api_key_name, base_url)
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
