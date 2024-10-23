from typing import Optional
from cohere import Client
from .secrets import resolve_secret


def find_api_key(plpy) -> str:
    return resolve_secret(plpy, "COHERE_API_KEY")


def make_client(plpy, api_key: Optional[str]) -> Client:
    if api_key is None:
        api_key = find_api_key(plpy)
    return Client(api_key)
