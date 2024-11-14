from cohere import Client

DEFAULT_KEY_NAME = "COHERE_API_KEY"


def make_client(api_key: str) -> Client:
    return Client(api_key)
