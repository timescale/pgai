from typing import Any, Literal

import pymupdf  # type: ignore
import pymupdf4llm  # type: ignore
from pydantic import BaseModel

from pgai.vectorizer.loading import LoadedDocument


class ParsingNone(BaseModel):
    implementation: Literal["none"]

    def parse(self, _1: dict[str, Any], payload: str | LoadedDocument) -> str:  # noqa: ARG002
        if isinstance(payload, LoadedDocument):
            raise ValueError(
                "Cannot chunk Document with parsing_none, "
                "use parsing_auto or parsing_pymupdf"
            )
        return payload


class ParsingAuto(BaseModel):
    implementation: Literal["auto"]

    def parse(self, row: dict[str, Any], payload: str | LoadedDocument) -> str:
        if isinstance(payload, LoadedDocument):
            return ParsingPyMuPDF(implementation="pymupdf").parse(row, payload)
        else:
            return payload


class ParsingPyMuPDF(BaseModel):
    implementation: Literal["pymupdf"]

    def parse(self, row: dict[str, Any], payload: LoadedDocument | str) -> str:  # noqa: ARG002
        if isinstance(payload, str):
            raise ValueError(
                "Column content must be a document to be parsed by pymupdf "
                "use parsing_auto or parsing_none instead"
            )

        if payload.file_type is None:
            raise ValueError("No file extension could be determined")

        if payload.file_type in ["txt", "md"]:  # type: ignore
            # no parsing is needed
            return payload.content.getvalue().decode("utf-8")

        with pymupdf.open(
            stream=payload.content, filetype=payload.file_type
        ) as pdf_document:  # type: ignore
            # Convert to markdown using pymupdf4llm
            md_text = pymupdf4llm.to_markdown(pdf_document)  # type: ignore

            return md_text
