import json
from collections.abc import Generator
from datetime import datetime
from typing import Any

import openai

DEFAULT_KEY_NAME = "OPENAI_API_KEY"


def get_openai_base_url(plpy) -> str | None:
    r = plpy.execute(
        "select pg_catalog.current_setting('ai.openai_base_url', true) as base_url"
    )
    if len(r) == 0:
        return None
    return r[0]["base_url"]


def make_client(
    plpy,
    api_key: str,
    client_config: dict[str, Any] | None = None,
) -> openai.Client:
    if client_config is None:
        client_config = {}
    if "base_url" not in client_config:
        client_config["base_url"] = get_openai_base_url(plpy)
    return openai.Client(api_key=api_key, **client_config)


def str_arg_to_dict(arg: str | None) -> dict | None:
    return json.loads(arg) if arg is not None else None


def create_kwargs(**kwargs) -> dict:
    kwargs_ = {}
    for k, v in kwargs.items():
        if v is not None:
            kwargs_[k] = v
    return kwargs_


def list_models(
    plpy,
    api_key: str,
    client_config: dict[str, Any] | None = None,
    extra_headers: str | None = None,
    extra_query: str | None = None,
) -> Generator[tuple[str, datetime, str], None, None]:
    client = make_client(plpy, api_key, client_config)
    from datetime import datetime, timezone

    kwargs = create_kwargs(
        extra_headers=str_arg_to_dict(extra_headers),
        extra_query=str_arg_to_dict(extra_query),
    )

    for model in client.models.list(**kwargs):
        created = datetime.fromtimestamp(model.created, timezone.utc)
        yield model.id, created, model.owned_by


def embed(
    plpy,
    client_config: dict[str, Any] | None,
    model: str,
    input: str | list[str] | list[int],
    api_key: str,
    dimensions: int | None = None,
    user: str | None = None,
    extra_headers: str | None = None,
    extra_query: str | None = None,
    extra_body: str | None = None,
) -> Generator[tuple[int, list[float]], None, None]:
    client = make_client(plpy, api_key, client_config)

    kwargs = create_kwargs(
        dimensions=dimensions,
        user=user,
        extra_headers=str_arg_to_dict(extra_headers),
        extra_query=str_arg_to_dict(extra_query),
        extra_body=str_arg_to_dict(extra_body),
    )
    response = client.embeddings.create(input=input, model=model, **kwargs)
    if not hasattr(response, "data"):
        return None
    for obj in response.data:
        yield obj.index, obj.embedding


def embed_with_raw_response(
    plpy,
    client_config: dict[str, Any] | None,
    model: str,
    input: str | list[str] | list[int],
    api_key: str,
    dimensions: int | None = None,
    user: str | None = None,
    extra_headers: str | None = None,
    extra_query: str | None = None,
    extra_body: str | None = None,
) -> str:
    client = make_client(plpy, api_key, client_config)

    kwargs = create_kwargs(
        dimensions=dimensions,
        user=user,
        extra_headers=str_arg_to_dict(extra_headers),
        extra_query=str_arg_to_dict(extra_query),
        extra_body=str_arg_to_dict(extra_body),
    )
    response = client.embeddings.with_raw_response.create(
        input=input, model=model, **kwargs
    )
    return response.text
