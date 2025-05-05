from collections.abc import Sequence

from pydantic import BaseModel


class EmbedRow(BaseModel):
    id: int
    content: str
    vector: Sequence[float] | None = None
