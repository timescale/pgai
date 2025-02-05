import io
from typing import Literal

import pymupdf4llm  # type: ignore
from filetype import filetype  # type: ignore
from pydantic import BaseModel
from pymupdf import pymupdf  # type: ignore


class AutoParser(BaseModel):
    implementation: Literal["auto"]

    def parse_file_content(self, file_content: bytes) -> str:
        file_like = io.BytesIO(file_content)
        kind = filetype.guess(file_like)  # type: ignore

        if kind is None:
            raise ValueError("Could not determine file type")

        file_like.seek(0)  # Reset buffer position after guessing file type
        with pymupdf.open(stream=file_like, filetype="pdf") as pdf_document:
            # Convert to markdown using pymupdf4llm
            md_text = pymupdf4llm.to_markdown(pdf_document)  # type: ignore
        return md_text
