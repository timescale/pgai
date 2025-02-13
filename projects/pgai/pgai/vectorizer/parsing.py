from abc import ABC, abstractmethod
from typing import Any, Literal

import pymupdf  # type: ignore
import pymupdf4llm  # type: ignore
from docling.datamodel.base_models import DocumentStream  # type: ignore
from docling.document_converter import DocumentConverter
from pydantic import BaseModel
from typing_extensions import override

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
            # return ParsingPyMuPDF(implementation="pymupdf").parse(row, payload)
            return ParsingDocling(implementation="docling").parse(row, payload)
        else:
            return payload


class BaseDocumentParsing(BaseModel, ABC):
    """Base class for document parsing implementations."""

    implementation: str

    def parse(self, row: dict[str, Any], payload: LoadedDocument | str) -> str:
        """
        Parse a document payload into a string representation.

        Args:
            row: Metadata about the document. The whole actual db row
            payload: Either a LoadedDocument or raw string content

        Returns:
            Parsed string content. Markdown preferable.

        Raises:
            ValueError: If payload type is invalid or file type cannot be determined
        """
        if isinstance(payload, str):
            raise ValueError(
                f"Column content must be a document to be parsed by "
                f"{self.implementation}, use parsing_auto or parsing_none instead"
            )

        if payload.file_type is None:
            raise ValueError("No file extension could be determined")

        if payload.file_type in ["txt", "md"]:
            return payload.content.getvalue().decode("utf-8")

        return self.parse_doc(row, payload)

    @abstractmethod
    def parse_doc(self, row: dict[str, Any], payload: LoadedDocument) -> str:
        """
        Parse a binary document into a string representation, Markdown preferable.
        Must be implemented by subclasses.
        """


class ParsingPyMuPDF(BaseDocumentParsing):
    """Document parsing implementation using PyMuPDF."""

    implementation: Literal["pymupdf"]  # type: ignore[reportIncompatibleVariableOverride]

    @override
    def parse_doc(self, row: dict[str, Any], payload: LoadedDocument) -> str:  # noqa: ARG002
        with pymupdf.open(
            stream=payload.content, filetype=payload.file_type
        ) as pdf_document:  # type: ignore
            return pymupdf4llm.to_markdown(pdf_document)  # type: ignore


class ParsingDocling(BaseDocumentParsing):
    """Document parsing implementation using Docling."""

    implementation: Literal["docling"]  # type: ignore[reportIncompatibleVariableOverride]

    @override
    def parse_doc(self, row: dict[str, Any], payload: LoadedDocument) -> str:  # noqa: ARG002
        source = DocumentStream(name=payload.file_path or "", stream=payload.content)
        result = DocumentConverter().convert(source)
        return result.document.export_to_markdown()
