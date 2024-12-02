from dataclasses import dataclass


@dataclass
class OpenAIEmbeddingConfig:
    model: str
    dimensions: int
    chat_user: str | None = None
    api_key_name: str | None = None


@dataclass
class OllamaEmbeddingConfig:
    model: str
    dimensions: int
    base_url: str | None = None
    truncate: bool | None = None
    keep_alive: str | None = None