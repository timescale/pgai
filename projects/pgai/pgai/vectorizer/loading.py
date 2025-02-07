from typing import Literal

from pydantic import BaseModel


class RowLoading(BaseModel):
    implementation: Literal["row"]
    column_name: str

    def load(self, row: dict[str, str]) -> str:
        return row[self.column_name]
