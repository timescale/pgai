import asyncio
import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from typing_extensions import override

from pgai.vectorizer.loading import LoadedDocument

# Thread pool for CPU-intensive parsing operations
max_workers = int(os.getenv("PARSING_MAX_WORKERS", 4))
_PARSING_EXECUTOR = ThreadPoolExecutor(
    max_workers=max_workers, thread_name_prefix="parsing"
)


class ParsingNone(BaseModel):
    implementation: Literal["none"]

    async def parse(self, _1: dict[str, Any], payload: str | LoadedDocument) -> str:  # noqa: ARG002
        if isinstance(payload, LoadedDocument):
            raise ValueError(
                "Cannot chunk Document with parsing_none, "
                "use parsing_auto or parsing_pymupdf"
            )
        return payload


class ParsingAuto(BaseModel):
    implementation: Literal["auto"]

    async def parse(self, row: dict[str, Any], payload: str | LoadedDocument) -> str:
        if isinstance(payload, LoadedDocument):
            if payload.file_type == "epub":
                # epub is not supported by docling, but by pymupdf
                return await ParsingPyMuPDF(implementation="pymupdf").parse(
                    row, payload
                )

            return await ParsingDocling(implementation="docling").parse(row, payload)
        else:
            return payload


class BaseDocumentParsing(BaseModel, ABC):
    """Base class for document parsing implementations."""

    implementation: str

    async def parse(self, row: dict[str, Any], payload: LoadedDocument | str) -> str:
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

        return await self.parse_doc(row, payload)

    @abstractmethod
    async def parse_doc(self, row: dict[str, Any], payload: LoadedDocument) -> str:
        """
        Parse a binary document into a string representation, Markdown preferable.
        Must be implemented by subclasses.
        """


class ParsingPyMuPDF(BaseDocumentParsing):
    """Document parsing implementation using PyMuPDF."""

    implementation: Literal["pymupdf"]  # type: ignore[reportIncompatibleVariableOverride]

    @override
    async def parse_doc(self, row: dict[str, Any], payload: LoadedDocument) -> str:  # noqa: ARG002
        # Run blocking parsing operation in thread pool
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _PARSING_EXECUTOR, self._parse_with_pymupdf, payload
        )

    def _parse_with_pymupdf(self, payload: LoadedDocument) -> str:
        """Synchronous pymupdf parsing to run in thread pool."""
        # Note: deferred import to avoid import overhead
        import pymupdf  # type: ignore
        import pymupdf4llm  # type: ignore

        with pymupdf.open(
            stream=payload.content, filetype=payload.file_type
        ) as pdf_document:  # type: ignore
            return pymupdf4llm.to_markdown(pdf_document)  # type: ignore


DEFAULT_CACHE_DIR = Path.home().joinpath(".cache/docling/models")
cache_dir = os.getenv("VECTORIZER_DOCLING_CACHE_DIR")
DOCLING_CACHE_DIR = DEFAULT_CACHE_DIR if cache_dir is None else Path(cache_dir)


class ParsingDocling(BaseDocumentParsing):
    """Document parsing implementation using Docling."""

    implementation: Literal["docling"]  # type: ignore[reportIncompatibleVariableOverride]
    cache_dir: Path | str = DOCLING_CACHE_DIR

    @override
    async def parse_doc(self, row: dict[str, Any], payload: LoadedDocument) -> str:  # noqa: ARG002
        # Run blocking parsing operation in thread pool
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _PARSING_EXECUTOR, self._parse_with_docling, payload
        )

    def _parse_with_docling(self, payload: LoadedDocument) -> str:
        """Synchronous docling parsing to run in thread pool."""
        # Note: deferred import to avoid import overhead
        from docling.datamodel.base_models import (
            DocumentStream,  # type: ignore
            InputFormat,
        )
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import (
            DocumentConverter,
            ImageFormatOption,
            PdfFormatOption,
        )

        basic_pipeline_options = PdfPipelineOptions(
            do_ocr=False,  # we do not want to do OCR in PDF (yet)
            artifacts_path=self.cache_dir if os.path.isdir(self.cache_dir) else None,
        )  # pyright: ignore[reportCallIssue]

        with_ocr_pipeline_options = basic_pipeline_options
        with_ocr_pipeline_options.do_ocr = True

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=basic_pipeline_options
                ),
                InputFormat.IMAGE: ImageFormatOption(
                    pipeline_options=with_ocr_pipeline_options
                ),
                # we don't need to configure the rest of the formats as they follow the
                # simple pipeline without external models, OCR, etc.
            }
        )

        source = DocumentStream(name=payload.file_path or "", stream=payload.content)
        result = converter.convert(source)
        return result.document.export_to_markdown()
