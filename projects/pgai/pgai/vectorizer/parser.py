from typing import Literal

from pydantic import BaseModel


class PyMuPDFParser(BaseModel):
    implementation: Literal["pymupdf"]
