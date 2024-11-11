from typing import Optional
from anthropic import Anthropic
from .secrets import reveal_secret


def find_api_key(plpy, api_key_name: Optional[str] = None) -> str:
    if api_key_name is None:
        api_key_name = "ANTHROPIC_API_KEY"
    key = reveal_secret(plpy, api_key_name)
    if key is None:
        plpy.error(f"missing {api_key_name} secret")
        # This line should never be reached, but it's here to make the type checker happy.
        return ""
    return key


def make_client(
    plpy,
    api_key: Optional[str] = None,
    api_key_name: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
) -> Anthropic:
    if api_key is None:
        api_key = find_api_key(plpy, api_key_name)
    args = {}
    if timeout is not None:
        args["timeout"] = timeout
    if max_retries is not None:
        args["max_retries"] = max_retries
    return Anthropic(api_key=api_key, base_url=base_url, **args)
