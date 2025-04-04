from typing import Literal

from pydantic import BaseModel


class DefaultDestination(BaseModel):
    implementation: Literal["default"]
    target_schema: str
    target_table: str


class SourceDestination(BaseModel):
    implementation: Literal["source"]
    embedding_column: str
