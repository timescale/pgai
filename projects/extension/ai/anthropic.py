from collections.abc import Generator
from datetime import datetime

from anthropic import Anthropic

DEFAULT_KEY_NAME = "ANTHROPIC_API_KEY"


def make_client(
    api_key: str,
    base_url: str | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
) -> Anthropic:
    args = {}
    if timeout is not None:
        args["timeout"] = timeout
    if max_retries is not None:
        args["max_retries"] = max_retries
    return Anthropic(api_key=api_key, base_url=base_url, **args)


def list_models(
    api_key: str,
    base_url: str | None = None,
) -> Generator[tuple[str, str, datetime], None, None]:
    client = make_client(api_key, base_url)

    for model in client.models.list():
        yield model.id, model.display_name, model.created_at
