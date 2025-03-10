from typing import Any, Literal

from pydantic.dataclasses import Field, dataclass

from pgai.vectorizer.chunking import BaseModel as ChunkingBaseModel
from pgai.vectorizer.chunking import (
    Chunker,
    LangChainCharacterTextSplitter,
    LangChainRecursiveCharacterTextSplitter,
)
from pgai.vectorizer.embedders import LiteLLM, Ollama, OpenAI, VoyageAI
from pgai.vectorizer.formatting import ChunkValue, PythonTemplate
from pgai.vectorizer.loading import ColumnLoading
from pgai.vectorizer.parsing import ParsingNone
from pgai.vectorizer.processing import ProcessingDefault

from . import register_migration


class LangChainCharacterTextSplitter_0_9(ChunkingBaseModel, Chunker):
    implementation: Literal["character_text_splitter"]
    separator: str
    chunk_size: int
    chunk_column: str
    chunk_overlap: int
    is_separator_regex: bool

    def into_chunks(self, row: dict[str, Any], payload: str) -> list[str]:
        pass


class LangChainRecursiveCharacterTextSplitter_0_9(ChunkingBaseModel, Chunker):
    implementation: Literal["recursive_character_text_splitter"]
    separators: list[str]
    chunk_size: int
    chunk_column: str
    chunk_overlap: int
    is_separator_regex: bool

    def into_chunks(self, row: dict[str, Any], payload: str) -> list[str]:
        pass


@dataclass
class Config_0_9:
    version: str
    embedding: OpenAI | Ollama | VoyageAI | LiteLLM
    processing: ProcessingDefault
    chunking: (
        LangChainCharacterTextSplitter_0_9 | LangChainRecursiveCharacterTextSplitter_0_9
    ) = Field(..., discriminator="implementation")
    formatting: PythonTemplate | ChunkValue = Field(..., discriminator="implementation")


@register_migration(
    "0.10.0",
    Config_0_9,
    "Migrate from no loading config to column_config, add "
    "parsing none, use proper chunking config",
)
def migrate_to_0_10_0(old_conf: Config_0_9) -> dict:
    # use the data as is from the previous version so we modify whatever is needed
    result = old_conf.__dict__.copy()

    result["loading"] = ColumnLoading(
        implementation="column", column_name=old_conf.chunking.chunk_column
    )
    result["parsing"] = ParsingNone(implementation="none")
    match old_conf.chunking.implementation:
        case "character_text_splitter":
            result["chunking"] = LangChainCharacterTextSplitter(
                implementation="character_text_splitter",
                separator=old_conf.chunking.separator,
                chunk_size=old_conf.chunking.chunk_size,
                chunk_overlap=old_conf.chunking.chunk_overlap,
                is_separator_regex=old_conf.chunking.is_separator_regex,
            )
        case "recursive_character_text_splitter":
            result["chunking"] = LangChainRecursiveCharacterTextSplitter(
                implementation="recursive_character_text_splitter",
                separators=old_conf.chunking.separators,
                chunk_size=old_conf.chunking.chunk_size,
                chunk_overlap=old_conf.chunking.chunk_overlap,
                is_separator_regex=old_conf.chunking.is_separator_regex,
            )

    return result
