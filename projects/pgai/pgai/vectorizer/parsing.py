import io
from typing import Any, Literal

import filetype  # type: ignore
import pymupdf  # type: ignore
import pymupdf4llm  # type: ignore
from pydantic import BaseModel


class ParsingNone(BaseModel):
    implementation: Literal["none"]

    def parse(self, _1: dict[str, Any], payload: str | bytes, _2: str | None) -> str:  # noqa: ARG002
        if isinstance(payload, bytes):
            raise ValueError(
                "Cannot chunk bytes with parsing_none, "
                "use parsing_auto or parsing_pymupdf"
            )
        return payload


class ParsingAuto(BaseModel):
    implementation: Literal["auto"]

    def parse(
        self, row: dict[str, Any], payload: str | bytes, column_name: str | None
    ) -> str:
        if isinstance(payload, bytes):
            return ParsingPyMuPDF(implementation="pymupdf").parse(
                row, payload, column_name
            )
        else:
            return payload


class ParsingPyMuPDF(BaseModel):
    implementation: Literal["pymupdf"]

    def parse(
        self, row: dict[str, Any], payload: bytes | str, column_name: str | None
    ) -> str:  # noqa: ARG002
        if isinstance(payload, str):
            raise ValueError(
                "Column content must be bytes to be parsed by pymupdf "
                "use parsing_auto or parsing_none instead"
            )
        with io.BytesIO() as file_like:
            file_like.write(memoryview(payload))
            kind = filetype.guess(file_like)  # type: ignore

            if kind:
                extension = kind.extension
            elif column_name is not None:
                # determine extension if possible
                extension = row[column_name].split(".")[-1]
            else:
                raise ValueError("No file extension could be determined")

            if extension in ["txt", "md"]:  # type: ignore
                # no parsing is needed
                return file_like.getvalue().decode("utf-8")

            file_like.seek(0)  # Reset buffer position after guessing file type
            with pymupdf.open(stream=file_like, filetype=extension) as pdf_document:  # type: ignore
                # Convert to markdown using pymupdf4llm
                md_text = pymupdf4llm.to_markdown(pdf_document)  # type: ignore

            return md_text
