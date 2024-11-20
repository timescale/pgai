from dataclasses import dataclass
from typing import Literal


@dataclass
class EmbeddingConfig:
    model: str
    dimensions: int
    chat_user: str | None = None
    api_key_name: str | None = None


@dataclass
class ChunkingConfig:
    chunk_column: str
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    separator: str | None = None
    separators: list[str] | None = None
    is_separator_regex: bool = False


@dataclass
class DiskANNIndexingConfig:
    min_rows: int | None = None
    storage_layout: Literal["memory_optimized", "plain"] | None = None
    num_neighbors: int | None = None
    search_list_size: int | None = None
    max_alpha: float | None = None
    num_dimensions: int | None = None
    num_bits_per_dimension: int | None = None
    create_when_queue_empty: bool | None = None


@dataclass
class HNSWIndexingConfig:
    min_rows: int | None = None
    opclass: Literal["vector_cosine_ops", "vector_l2_ops", "vector_ip_ops"] | None = (
        None
    )
    m: int | None = None
    ef_construction: int | None = None
    create_when_queue_empty: bool | None = None


@dataclass
class NoScheduling:
    pass


@dataclass
class SchedulingConfig:
    schedule_interval: str | None = None
    initial_start: str | None = None
    fixed_schedule: bool | None = None
    timezone: str | None = None


@dataclass
class ProcessingConfig:
    batch_size: int | None = None
    concurrency: int | None = None
