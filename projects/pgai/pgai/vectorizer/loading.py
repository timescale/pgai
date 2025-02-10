from typing import Literal

import smart_open
from pydantic import BaseModel


class RowLoading(BaseModel):
    implementation: Literal["row"]
    column_name: str

    def load(self, row: dict[str, str]) -> str:
        return row[self.column_name] or ""


class DocumentLoading(BaseModel):
    implementation: Literal["document"]
    column_name: str

    def load(self, row: dict[str, str]) -> str:
        return smart_open.open(row[self.column_name], "rb").read()
