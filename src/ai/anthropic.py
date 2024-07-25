from typing import Optional
from anthropic import Anthropic


def find_api_key(plpy) -> str:
    r = plpy.execute(
        "select pg_catalog.current_setting('ai.anthropic_api_key', true) as api_key"
    )
    if len(r) >= 0:
        return r[0]["api_key"]
    else:
        plpy.error("missing api key")


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
