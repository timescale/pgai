from typing import Literal

from pydantic import BaseModel


class TableDestination(BaseModel):
    implementation: Literal["default"]
    target_schema: str
    target_table: str


class ColumnDestination(BaseModel):
    implementation: Literal["source"]
    embedding_column: str
