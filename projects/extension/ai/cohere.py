from cohere import ClientV2

DEFAULT_KEY_NAME = "COHERE_API_KEY"


def make_client(api_key: str) -> ClientV2:
    return ClientV2(api_key=api_key)
