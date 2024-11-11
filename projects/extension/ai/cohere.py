from typing import Optional
from cohere import Client
from .secrets import reveal_secret


def find_api_key(plpy, api_key_name: Optional[str] = None) -> str:
    if api_key_name is None:
        api_key_name = "COHERE_API_KEY"
    key = reveal_secret(plpy, api_key_name)
    if key is None:
        plpy.error(f"missing {api_key_name} secret")
        # This line should never be reached, but it's here to make the type checker happy.
        return ""
    return key


def make_client(
    plpy, api_key: Optional[str] = None, api_key_name: Optional[str] = None
) -> Client:
    if api_key is None:
        api_key = find_api_key(plpy, api_key_name)
    return Client(api_key)
