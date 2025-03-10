from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from functools import cached_property
from typing import Any, Literal, TypeVar, overload

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


# Type variable for Pydantic config models
C = TypeVar("C", bound=BaseModel)

# Type definition for chunking functions
ChunkerFunc = Callable[
    [dict[str, Any], dict[str, Any]], list[str] | Awaitable[list[str]]
]

# Global registry for chunking functions and their config models
registered_chunkers: dict[str, ChunkerFunc] = dict()
chunker_config_models: dict[str, type[BaseModel]] = dict()


@overload
def chunker(func: ChunkerFunc) -> ChunkerFunc: ...


@overload
def chunker(
    *, name: str | None = None, config_model: type[C] | None = None
) -> Callable[[ChunkerFunc], ChunkerFunc]: ...


def chunker(
    func: ChunkerFunc | None = None,
    *,  # enforce keyword-only arguments
    name: str | None = None,
    config_model: type[BaseModel] | None = None,
) -> ChunkerFunc | Callable[[ChunkerFunc], ChunkerFunc]:
    """
    Decorator to register chunking functions in the global registry.

    A chunking function takes a source row and configuration and returns a list of chunks.

    Example:
    ```python
    class MyChunkerConfig(ChunkerConfig):
        chunk_column: str
        chunk_size: int = 1000
        chunk_overlap: int = 200


    @chunker(name="my_custom_chunker", config_model=MyChunkerConfig)
    def my_chunking_function(item: dict[str, Any], config: dict[str, Any]) -> list[str]:
        text = item[config["chunk_column"]]
        # Custom chunking logic
        return chunks
    ```
    """

    def decorator(f: ChunkerFunc) -> ChunkerFunc:
        registration_name = name if name is not None else f.__name__
        registered_chunkers[registration_name] = f

        # Store the config model if provided
        if config_model is not None:
            chunker_config_models[registration_name] = config_model

        return f

    if func is not None:
        return decorator(func)

    return decorator


class CharacterTextSplitterConfig(BaseModel):
    """Configuration for character text splitter"""

    separator: str
    chunk_size: int
    chunk_column: str
    chunk_overlap: int = 0
    is_separator_regex: bool = False


@chunker(name="character_text_splitter", config_model=CharacterTextSplitterConfig)
def character_text_splitter(item: dict[str, Any], config: dict[str, Any]) -> list[str]:
    """
    Default implementation of character text splitter using the decorator pattern.
    """
    chunker = CharacterTextSplitter(
        separator=config["separator"],
        chunk_size=config["chunk_size"],
        chunk_overlap=config["chunk_overlap"],
        is_separator_regex=config.get("is_separator_regex", False),
    )
    text = item[config["chunk_column"]] or ""
    return chunker.split_text(text)


class RecursiveCharacterTextSplitterConfig(BaseModel):
    """Configuration for recursive character text splitter"""

    separators: list[str]
    chunk_size: int
    chunk_column: str
    chunk_overlap: int = 0
    is_separator_regex: bool = False


@chunker(
    name="recursive_character_text_splitter",
    config_model=RecursiveCharacterTextSplitterConfig,
)
def recursive_character_text_splitter(
    item: dict[str, Any], config: dict[str, Any]
) -> list[str]:
    """
    Default implementation of recursive character text splitter using the decorator pattern.
    """
    chunker = RecursiveCharacterTextSplitter(
        separators=config["separators"],
        chunk_size=config["chunk_size"],
        chunk_overlap=config["chunk_overlap"],
        is_separator_regex=config.get("is_separator_regex", False),
    )
    text = item[config["chunk_column"]] or ""
    return chunker.split_text(text)
