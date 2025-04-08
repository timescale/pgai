from abc import ABC, abstractmethod
from functools import cached_property
from typing import Any, Literal, Protocol

from pydantic import BaseModel
from typing_extensions import override


class SplitTextProtocol(Protocol):
    def split_text(self, text: str) -> list[str]:
        """Split text into multiple components."""
        ...


class Chunker(ABC):
    """
    Abstract base class for chunking functionality.

    Defines the interface for any chunker that breaks a dictionary item into
    chunks of text.
    """

    @abstractmethod
    def into_chunks(self, row: dict[str, Any], payload: str) -> list[str]:
        """
        Breaks the provided dictionary item into chunks of text.

        Args:
            item (dict[str, Any]): A dictionary representing a database row,
                where keys are column names and values are the corresponding
                data.

        Returns:
            list[str]: A list of chunked strings.
        """


class NoneChunker(BaseModel, Chunker):
    """
    A chunker implementation that does not chunk the text.

    This chunker passes the text through unmodified as a single chunk,
    skipping any chunking logic and preserving the document as-is.

    Attributes:
        implementation (Literal): A literal value identifying the implementation.
    """

    implementation: Literal["none"]

    @override
    def into_chunks(self, row: dict[str, Any], payload: str) -> list[str]:
        """
        Returns the text as a single chunk without any processing.

        Args:
            row (dict[str, Any]): A dictionary representing a database row,
                where keys are column names and values are the corresponding
                data.
            payload (str): The text content to be chunked.

        Returns:
            list[str]: A list containing just the original text as a single chunk.
        """
        return [payload]


class LangChainCharacterTextSplitter(BaseModel, Chunker):
    """
    A chunker implementation using LangChain's CharacterTextSplitter.

    This class chunks text based on a separator, chunk size, and chunk overlap,
    using the CharacterTextSplitter from the LangChain library.

    Attributes:
        implementation (Literal): A literal value identifying the implementation.
        separator (str): The string used to split the text into chunks.
        chunk_size (int): The maximum size of each chunk.
        chunk_overlap (int): The number of characters that overlap between chunks.
        is_separator_regex (bool): Indicates whether the separator is a regular
            expression.
    """

    implementation: Literal["character_text_splitter"]
    separator: str
    chunk_size: int
    chunk_overlap: int
    is_separator_regex: bool

    @cached_property
    def _chunker(self) -> SplitTextProtocol:
        # Note: deferred import to avoid import overhead
        from langchain_text_splitters import CharacterTextSplitter

        return CharacterTextSplitter(
            separator=self.separator,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            is_separator_regex=self.is_separator_regex,
        )

    @override
    def into_chunks(self, row: dict[str, Any], payload: str) -> list[str]:
        """
        Splits the text from the provided item into chunks using CharacterTextSplitter.

        Args:
            item (dict[str, Any]): A dictionary representing a database row,
                where keys are column names and values are the corresponding
                data.

        Returns:
            list[str]: A list of chunked strings.
        """
        return self._chunker.split_text(payload)


class LangChainRecursiveCharacterTextSplitter(BaseModel, Chunker):
    """
    A chunker implementation using LangChain's CharacterTextSplitter.

    This class chunks text based on a separator, chunk size, and chunk overlap,
    using the CharacterTextSplitter from the LangChain library.

    Attributes:
        implementation (Literal): A literal value identifying the implementation.
        separators (list[str]): A list of strings used to split the text into chunks.
        chunk_size (int): The maximum size of each chunk.
        chunk_overlap (int): The number of characters that overlap between chunks.
        is_separator_regex (bool): Indicates whether the separator is a regular
            expression.
    """

    implementation: Literal["recursive_character_text_splitter"]
    separators: list[str]
    chunk_size: int
    chunk_overlap: int
    is_separator_regex: bool

    @cached_property
    def _chunker(self) -> SplitTextProtocol:
        # Note: deferred import to avoid import overhead
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        return RecursiveCharacterTextSplitter(
            separators=self.separators,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            is_separator_regex=self.is_separator_regex,
        )

    @override
    def into_chunks(self, row: dict[str, Any], payload: str) -> list[str]:
        """
        Recursively splits the text from the provided item into chunks using
        RecursiveCharacterTextSplitter.

        Args:
            item (dict[str, Any]): A dictionary representing a database row,
                where keys are column names and values are the corresponding
                data.

        Returns:
            list[str]: A list of chunked strings.
        """
        return self._chunker.split_text(payload)
