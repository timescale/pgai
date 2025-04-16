from typing import Literal

from pydantic import BaseModel, ConfigDict

# These classes are both frozen so that they are hashable and
# can be used as keys for the sql building chaches.


class TableDestination(BaseModel):
    model_config = ConfigDict(frozen=True)
    implementation: Literal["table"]
    target_schema: str
    target_table: str


class ColumnDestination(BaseModel):
    model_config = ConfigDict(frozen=True)
    implementation: Literal["column"]
    embedding_column: str
