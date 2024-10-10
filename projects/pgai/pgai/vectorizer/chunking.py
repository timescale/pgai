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
    @abstractmethod
    def into_chunks(self, item: dict[str, Any]) -> list[str]:
        pass


class LangChainCharacterTextSplitter(BaseModel, Chunker):
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
        return self._chunker.split_text(item[self.chunk_column])


class LangChainRecursiveCharacterTextSplitter(BaseModel, Chunker):
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
        return self._chunker.split_text(item[self.chunk_column])
