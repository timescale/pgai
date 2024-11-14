from typing import Optional
from anthropic import Anthropic

DEFAULT_KEY_NAME = "ANTHROPIC_API_KEY"


def make_client(
    api_key: str,
    base_url: Optional[str] = None,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
) -> Anthropic:
    args = {}
    if timeout is not None:
        args["timeout"] = timeout
    if max_retries is not None:
        args["max_retries"] = max_retries
    return Anthropic(api_key=api_key, base_url=base_url, **args)
