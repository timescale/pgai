from typing import Optional
from anthropic import Anthropic
from .secrets import reveal_secret


def find_api_key(plpy) -> str:
    key = reveal_secret(plpy, "ANTHROPIC_API_KEY")
    if key is None:
        plpy.error("missing ANTHROPIC_API_KEY secret")
    return key


def make_client(
    plpy,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
) -> Anthropic:
    if api_key is None:
        api_key = find_api_key(plpy)
    args = {}
    if timeout is not None:
        args["timeout"] = timeout
    if max_retries is not None:
        args["max_retries"] = max_retries
    return Anthropic(api_key=api_key, base_url=base_url, **args)
