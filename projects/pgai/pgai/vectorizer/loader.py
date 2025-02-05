from typing import Any, Literal

import smart_open  # type: ignore
from pydantic import BaseModel


class DocumentLoader(BaseModel):
    implementation: Literal["document"]
    file_uri_column: str

    def load(self, item: dict[str, Any]) -> bytes:
        url = item[self.file_uri_column]
        with smart_open.open(url, "rb") as file:  # type: ignore
            content: bytes = file.read()  # type: ignore
        return content  # type: ignore
