from abc import ABC, abstractmethod
from functools import cached_property
from typing import Any, Literal

from langchain_text_splitters import (
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
)
from pydantic import BaseModel
from typing_extensions import override


class Chunker(ABC):
    """
    Abstract base class for chunking functionality.

    Defines the interface for any chunker that breaks a dictionary item into
    chunks of text.
    """

    @abstractmethod
    def into_chunks(self, item: dict[str, Any]) -> list[str]:
        """
        Breaks the provided dictionary item into chunks of text.

        Args:
            item (dict[str, Any]): A dictionary representing a database row,
                where keys are column names and values are the corresponding
                data.

        Returns:
            list[str]: A list of chunked strings.
        """


class LangChainCharacterTextSplitter(BaseModel, Chunker):
    """
    A chunker implementation using LangChain's CharacterTextSplitter.

    This class chunks text based on a separator, chunk size, and chunk overlap,
    using the CharacterTextSplitter from the LangChain library.

    Attributes:
        implementation (Literal): A literal value identifying the implementation.
        separator (str): The string used to split the text into chunks.
        chunk_size (int): The maximum size of each chunk.
        chunk_column (str): The dictionary key corresponding to the text that
            needs to be chunked.
        chunk_overlap (int): The number of characters that overlap between chunks.
        is_separator_regex (bool): Indicates whether the separator is a regular
            expression.
    """

    implementation: Literal["character_text_splitter"]
    separator: str
    chunk_size: int
    chunk_column: str
    chunk_overlap: int
    is_separator_regex: bool

    @cached_property
    def _chunker(self) -> CharacterTextSplitter:
        return CharacterTextSplitter(
            separator=self.separator,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            is_separator_regex=self.is_separator_regex,
        )

    @override
    def into_chunks(self, item: dict[str, Any]) -> list[str]:
        """
        Splits the text from the provided item into chunks using CharacterTextSplitter.

        Args:
            item (dict[str, Any]): A dictionary representing a database row,
                where keys are column names and values are the corresponding
                data.

        Returns:
            list[str]: A list of chunked strings.
        """
        text = item[self.chunk_column] or ""
        return self._chunker.split_text(text)


class LangChainRecursiveCharacterTextSplitter(BaseModel, Chunker):
    """
    Splits the text from the provided item into chunks using CharacterTextSplitter.

    Args:
        item (dict[str, Any]): A dictionary representing a database row,
            where keys are column names and values are the corresponding
            data.

    Returns:
        list[str]: A list of chunked strings.
    """

    implementation: Literal["recursive_character_text_splitter"]
    separators: list[str]
    chunk_size: int
    chunk_column: str
    chunk_overlap: int
    is_separator_regex: bool

    @cached_property
    def _chunker(self) -> RecursiveCharacterTextSplitter:
        return RecursiveCharacterTextSplitter(
            separators=self.separators,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            is_separator_regex=self.is_separator_regex,
        )

    @override
    def into_chunks(self, item: dict[str, Any]) -> list[str]:
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
        text = item[self.chunk_column] or ""
        return self._chunker.split_text(text)
