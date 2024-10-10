from pydantic.dataclasses import dataclass


@dataclass
class Secrets:
    """Secrets to be mapped into the event payload."""

    OPENAI_API_KEY: str | None = None
