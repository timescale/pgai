import io
from typing import Any, Literal

import filetype
import pymupdf
import pymupdf4llm
from pydantic import BaseModel


class ParsingNone(BaseModel):
    implementation: Literal["none"]

    def parse(self, row: dict[str, Any], payload: str | bytes) -> str:  # noqa: ARG002
        if isinstance(payload, bytes):
            raise ValueError(
                "Cannot chunk bytes with parsing_none, "
                "use parsing_auto or parsing_pymupdf"
            )
        return payload


class ParsingAuto(BaseModel):
    implementation: Literal["auto"]

    def parse(self, row: dict[str, Any], payload: str | bytes) -> str:
        if isinstance(payload, bytes):
            return ParsingPyMuPDF(implementation="pymupdf").parse(row, payload)
        else:
            return payload


class ParsingPyMuPDF(BaseModel):
    implementation: Literal["pymupdf"]

    def parse(self, row: dict[str, Any], payload: bytes | str) -> str:  # noqa: ARG002
        if isinstance(payload, str):
            raise ValueError(
                "Column content must be bytes to be parsed by pymupdf "
                "use parsing_auto or parsing_none instead"
            )
        file_like = io.BytesIO(payload)
        kind = filetype.guess(file_like)  # type: ignore

        if kind is None:
            raise ValueError("Could not determine file type")

        file_like.seek(0)  # Reset buffer position after guessing file type
        with pymupdf.open(stream=file_like, filetype="pdf") as pdf_document:
            # Convert to markdown using pymupdf4llm
            md_text = pymupdf4llm.to_markdown(pdf_document)  # type: ignore
        return md_text
