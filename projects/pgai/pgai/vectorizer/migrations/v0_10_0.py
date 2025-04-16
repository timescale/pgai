from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import override

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

from ..destination import TableDestination
from . import register_migration


class LangChainCharacterTextSplitter_0_9(BaseModel, Chunker):
    implementation: Literal["character_text_splitter"]
    separator: str
    chunk_size: int
    chunk_column: str
    chunk_overlap: int
    is_separator_regex: bool

    @override
    def into_chunks(self, row: dict[str, Any], payload: str) -> list[str]:
        return []  # noop


class LangChainRecursiveCharacterTextSplitter_0_9(BaseModel, Chunker):
    implementation: Literal["recursive_character_text_splitter"]
    separators: list[str]
    chunk_size: int
    chunk_column: str
    chunk_overlap: int
    is_separator_regex: bool

    @override
    def into_chunks(self, row: dict[str, Any], payload: str) -> list[str]:
        return []  # noop


class Config_0_9(BaseModel):
    model_config = ConfigDict(extra="allow")
    version: str
    embedding: OpenAI | Ollama | VoyageAI | LiteLLM
    processing: ProcessingDefault
    chunking: (
        LangChainCharacterTextSplitter_0_9 | LangChainRecursiveCharacterTextSplitter_0_9
    ) = Field(..., discriminator="implementation")
    formatting: PythonTemplate | ChunkValue = Field(..., discriminator="implementation")


class Vectorizer_0_9(BaseModel):
    model_config = ConfigDict(extra="allow")
    config: Config_0_9
    target_table: str
    target_schema: str


@register_migration(
    "0.10.0",
    Vectorizer_0_9,
    "Migrate from no loading config to column_config, add "
    "parsing none, use proper chunking config",
)
def migrate_to_0_10_0(old_vectorizer: Vectorizer_0_9) -> dict[str, Any]:
    # use the data as is from the previous version so we modify whatever is needed
    result = old_vectorizer.model_dump()
    old_config = old_vectorizer.config

    result["config"]["loading"] = ColumnLoading(
        implementation="column", column_name=old_config.chunking.chunk_column
    )
    result["config"]["parsing"] = ParsingNone(implementation="none")
    match old_vectorizer.config.chunking.implementation:
        case "character_text_splitter":
            result["config"]["chunking"] = LangChainCharacterTextSplitter(
                implementation="character_text_splitter",
                separator=old_config.chunking.separator,  # type: ignore[reportUnknownVariableType]
                chunk_size=old_config.chunking.chunk_size,
                chunk_overlap=old_config.chunking.chunk_overlap,
                is_separator_regex=old_config.chunking.is_separator_regex,
            )
        case "recursive_character_text_splitter":
            result["config"]["chunking"] = LangChainRecursiveCharacterTextSplitter(
                implementation="recursive_character_text_splitter",
                separators=old_config.chunking.separators,  # type: ignore[reportUnknownVariableType]
                chunk_size=old_config.chunking.chunk_size,
                chunk_overlap=old_config.chunking.chunk_overlap,
                is_separator_regex=old_config.chunking.is_separator_regex,
            )
        case _:
            raise ValueError(
                f"Unknown chunking implementation: {old_config.chunking.implementation}"
            )

    result["config"]["destination"] = TableDestination(
        implementation="table",
        target_schema=old_vectorizer.target_schema,
        target_table=old_vectorizer.target_table,
    )

    return result
