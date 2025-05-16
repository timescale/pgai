"""Models for representing data being vectorized in the semantic catalog.

This module contains the data models used for representing content that will be
converted to vector embeddings for the semantic catalog.
"""

from collections.abc import Sequence

from pydantic import BaseModel


class EmbedRow(BaseModel):
    """Model representing a row of data to be embedded.

    This class holds the content to be embedded and its resulting vector embedding.
    It serves as the data structure for passing content to embedding services and
    storing the resulting vector embeddings.

    Attributes:
        id: Database ID of the item being embedded.
        content: Text content to be converted to a vector embedding.
        vector: The resulting vector embedding (None until embedding is performed).
    """

    id: int
    content: str
    vector: Sequence[float] | None = None
