import tokenizers

class EmbeddingsObject:
    embeddings: list[list[float]]
    total_tokens: int

class Client:
    """Voyage AI Client

    Args:
        api_key (str): Your API key.
        max_retries (int): Maximum number of retries if API call fails.
        timeout (float): Timeout in seconds.
    """
    def __init__(
        self,
        api_key: str | None = ...,
        max_retries: int = ...,
        timeout: float | None = ...,
    ) -> None: ...
    def tokenizer(self, model: str) -> tokenizers.Tokenizer: ...

class AsyncClient:
    """Voyage AI Async Client

    Args:
        api_key (str): Your API key.
        max_retries (int): Maximum number of retries if API call fails.
        timeout (float): Timeout in seconds.
    """
    def __init__(
        self,
        api_key: str | None = ...,
        max_retries: int = ...,
        timeout: float | None = ...,
    ) -> None: ...
    async def embed(
        self,
        texts: list[str],
        model: str | None = ...,
        input_type: str | None = ...,
        truncation: bool = ...,
    ) -> EmbeddingsObject: ...
