from typing import Optional
from cohere import Client


def find_api_key(plpy) -> str:
    r = plpy.execute(
        "select pg_catalog.current_setting('ai.cohere_api_key', true) as api_key"
    )
    if len(r) == 0:
        plpy.error("missing api key")
    return r[0]["api_key"]


def make_client(plpy, api_key: Optional[str]) -> Client:
    if api_key is None:
        api_key = find_api_key(plpy)
    return Client(api_key)
