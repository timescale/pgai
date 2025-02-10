from pydantic import BaseModel
from typing import Literal
import io
import filetype
import pymupdf
import pymupdf4llm


class ParsingNone(BaseModel):
    implementation: Literal["none"]

    def parse(self, row: dict[str, str], payload: str) -> str:
        return payload


class ParsingAuto(BaseModel):
    implementation: Literal["auto"]

    def parse(self, row: dict[str, str], payload: str | bytes) -> str:
        if isinstance(payload, bytes):
            return ParsingPyMuPDF(implementation="pymupdf").parse(row, payload)
        else:
            return payload

class ParsingPyMuPDF(BaseModel):
    implementation: Literal["pymupdf"]

    def parse(self, row: dict[str, str], payload: bytes) -> str:
        file_like = io.BytesIO(payload)
        kind = filetype.guess(file_like)  # type: ignore

        if kind is None:
            raise ValueError("Could not determine file type")

        file_like.seek(0)  # Reset buffer position after guessing file type
        with pymupdf.open(stream=file_like, filetype="pdf") as pdf_document:
            # Convert to markdown using pymupdf4llm
            md_text = pymupdf4llm.to_markdown(pdf_document)  # type: ignore
        return md_text

    
    