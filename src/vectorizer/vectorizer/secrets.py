from typing import Optional

from pydantic.dataclasses import dataclass


@dataclass
class Secrets:
    """Secrets to be mapped into the event payload."""

    OPENAI_API_KEY: Optional[str] = None
