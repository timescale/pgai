from typing import Optional
from cohere import Client
from .secrets import reveal_secret


def find_api_key(plpy) -> str:
    key = reveal_secret(plpy, "COHERE_API_KEY")
    if key is None:
        plpy.error("missing COHERE_API_KEY secret")
    return key


def make_client(plpy, api_key: Optional[str]) -> Client:
    if api_key is None:
        api_key = find_api_key(plpy)
    return Client(api_key)
