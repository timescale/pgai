from typing import Annotated, Literal

from annotated_types import Gt, Le
from openai import BaseModel


class BaseOpenAIConfig(BaseModel):
    """Base configuration shared between runtime and migration OpenAI configs"""
    model: str
    dimensions: int


class BaseOllamaConfig(BaseModel):
    model: str
    dimensions: int
    base_url: str | None = None
    keep_alive: str | None = None


class BaseVoyageAIConfig(BaseModel):
    model: str
    dimensions: int
    input_type: Literal["document"] | Literal["query"] | None = None


class ChunkingCharacterTextSplitter(BaseModel):
    chunk_column: str
    chunk_size: int
    chunk_overlap: int
    separator: str
    is_separator_regex: bool


class ChunkingRecursiveCharacterTextSplitter(BaseModel):
    separators: list[str]
    chunk_size: int
    chunk_column: str
    chunk_overlap: int
    is_separator_regex: bool


class BasePythonTemplate(BaseModel):
    template: str


class BaseProcessing(BaseModel):
    batch_size: Annotated[int, Gt(gt=0), Le(le=2048)] = 50
    concurrency: Annotated[int, Gt(gt=0), Le(le=10)] = 1