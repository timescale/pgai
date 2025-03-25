from typing import Literal

from pydantic import BaseModel


class DefaultDestination(BaseModel):
    implementation: str = Literal["default"]
    target_schema: str = None
    target_table: str = None
    
class SourceDestination(BaseModel):
    embedding_column: str