from dataclasses import dataclass
from io import BytesIO
from typing import Literal

import smart_open  # type: ignore
from filetype import filetype
from pydantic import BaseModel


@dataclass
class LoadedDocument:
    content: BytesIO
    file_path: str | None = None
    file_type: str | None = None


def guess_filetype(file_like: BytesIO, file_path: str | None = None) -> str | None:
    guess = filetype.guess(file_like)
    file_like.seek(0)
    if guess is None:
        if file_path is None:
            return None
        return file_path.split(".")[-1]
    return guess.extension


class RowLoading(BaseModel):
    implementation: Literal["row"]
    column_name: str

    def load(self, row: dict[str, str]) -> str | LoadedDocument:
        content = row[self.column_name] or ""
        if isinstance(content, bytes):
            content = BytesIO(content)
            return LoadedDocument(
                content=content,
                file_type=guess_filetype(content),
            )
        return content


class DocumentLoading(BaseModel):
    implementation: Literal["document"]
    column_name: str

    def load(self, row: dict[str, str]) -> LoadedDocument:
        content = BytesIO(
            smart_open.open(row[self.column_name], "rb").read()  # type: ignore
        )
        return LoadedDocument(
            content=content,
            file_path=row[self.column_name],
            file_type=guess_filetype(content, row[self.column_name]),
        )
