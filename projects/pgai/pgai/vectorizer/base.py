from datetime import timedelta
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


class BaseTimescaleScheduling(BaseModel):
    schedule_interval: timedelta | None = None
    initial_start: str | None = None
    job_id: int | None = None
    fixed_schedule: bool
    timezone: str | None = None


class BaseDiskANNIndexing(BaseModel):
    min_rows: int
    storage_layout: Literal["memory_optimized", "plain"] | None = None
    num_neighbors: int | None = None
    search_list_size: int | None = None
    max_alpha: float | None = None
    num_dimensions: int | None = None
    num_bits_per_dimension: int | None = None
    create_when_queue_empty: bool


class BaseHNSWIndexing(BaseModel):
    min_rows: int
    opclass: Literal["vector_cosine_ops", "vector_l1_ops", "vector_ip_ops"]
    m: int
    ef_construction: int
    create_when_queue_empty: bool
