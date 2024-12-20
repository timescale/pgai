import re
from dataclasses import dataclass, fields
from datetime import timedelta
from typing import ClassVar, Protocol, runtime_checkable, Literal

from pydantic import BaseModel

from pgai.vectorizer.base import (
    BaseOllamaConfig,
    BaseOpenAIConfig,
    BaseProcessing,
    BasePythonTemplate,
    BaseVoyageAIConfig,
    ChunkingCharacterTextSplitter,
    ChunkingRecursiveCharacterTextSplitter,
)


@runtime_checkable
class SQLArgumentProvider(Protocol):
    def to_sql_argument(self) -> str: ...


@runtime_checkable
class PythonArgProvider(Protocol):
    def to_python_arg(self) -> str: ...


def format_sql_params(params: dict[str, str | None | bool | list[str]]) -> str:
    """Format dictionary of parameters into SQL argument string without any quoting."""
    formatted: list[str] = []
    for key, value in params.items():
        if value is None:
            continue
        elif isinstance(value, bool):
            formatted.append(f"{key}=>{str(value).lower()}")
        elif isinstance(value, list):
            array_list = ",".join(f"E'{v}'" for v in value)
            formatted.append(f"{key}=>ARRAY[{array_list}]")
        elif isinstance(value, timedelta):
            formatted.append(f"{key}=>'{value.seconds} seconds'")
        else:
            formatted.append(f"{key}=> '{value}'")
    return ", ".join(formatted)


class SQLArgumentMixin:
    arg_type: ClassVar[str]
    function_name: ClassVar[str | None] = None

    def to_sql_argument(self) -> str:
        # Get all fields including from parent classes
        params = {}
        for field_name, _field in self.model_fields.items():  # type: ignore
            if field_name != "arg_type":
                value = getattr(self, field_name)  # type: ignore
                if value is not None:
                    params[field_name] = value

        if self.function_name:
            fn_name = self.function_name
        else:
            base_name = self.__class__.__name__
            # Convert camelCase to snake_case
            base_name = re.sub("([a-z0-9])([A-Z])", r"\1_\2", base_name).lower()
            # Remove 'config' and clean up any double underscores
            base_name = base_name.replace("config", "").strip("_")
            # Remove any duplicate underscores that might have been created
            fn_name = f"{self.arg_type}_{base_name}"

        return f", {self.arg_type} => ai.{fn_name}({format_sql_params(params)})"  # type: ignore


class OpenAIConfig(BaseOpenAIConfig, SQLArgumentMixin):
    arg_type: ClassVar[str] = "embedding"
    function_name: ClassVar[str] = "embedding_openai"  # type: ignore
    chat_user: str | None = None
    api_key_name: str | None = None


class VoyageAIConfig(BaseVoyageAIConfig, SQLArgumentMixin):
    arg_type: ClassVar[str] = "embedding"
    function_name: ClassVar[str] = "embedding_voyageai"  # type: ignore
    api_key_name: str | None = None


class OllamaConfig(BaseOllamaConfig, SQLArgumentMixin):
    arg_type: ClassVar[str] = "embedding"


class CharacterTextSplitterConfig(ChunkingCharacterTextSplitter, SQLArgumentMixin):
    arg_type: ClassVar[str] = "chunking"


class RecursiveCharacterTextSplitterConfig(
    ChunkingRecursiveCharacterTextSplitter, SQLArgumentMixin
):
    arg_type: ClassVar[str] = "chunking"


class ChunkValueConfig:
    arg_type: ClassVar[str] = "formatting"

    def to_sql_argument(self) -> str:
        return f", {self.arg_type: ClassVar[str]} => ai.formatting_chunk_value()"


class PythonTemplateConfig(BasePythonTemplate, SQLArgumentMixin):
    arg_type: ClassVar[str] = "formatting"


class NoIndexingConfig:
    arg_type: ClassVar[str] = "indexing"

    def to_sql_argument(self) -> str:
        return f", {self.arg_type: ClassVar[str]} => ai.indexing_none()"


class DiskANNIndexingConfig(BaseModel, SQLArgumentMixin):
    arg_type: ClassVar[str] = "indexing"
    function_name: ClassVar[str] = "indexing_diskann"  # type: ignore
    min_rows: int
    storage_layout: Literal["memory_optimized", "plain"] | None = None
    num_neighbors: int | None = None
    search_list_size: int | None = None
    max_alpha: float | None = None
    num_dimensions: int | None = None
    num_bits_per_dimension: int | None = None
    create_when_queue_empty: bool | None = None


class HNSWIndexingConfig(BaseModel, SQLArgumentMixin):
    arg_type: ClassVar[str] = "indexing"
    function_name: ClassVar[str] = "indexing_hnsw"  # type: ignore
    min_rows: int | None = None
    opclass: Literal["vector_cosine_ops", "vector_l1_ops", "vector_ip_ops"] | None = None
    m: int | None = None
    ef_construction: int | None = None
    create_when_queue_empty: bool | None = None


class NoSchedulingConfig:
    arg_type: ClassVar[str] = "scheduling"

    def to_sql_argument(self) -> str:
        return f", {self.arg_type: ClassVar[str]} => ai.scheduling_none()"


class TimescaleSchedulingConfig(BaseModel, SQLArgumentMixin):
    arg_type: ClassVar[str] = "scheduling"
    function_name: ClassVar[str] = "scheduling_timescaledb"  # type: ignore
    
    schedule_interval: timedelta | None = None
    initial_start: str | None = None
    job_id: int | None = None
    fixed_schedule: bool | None = None
    timezone: str | None = None


class ProcessingConfig(BaseProcessing, SQLArgumentMixin):
    arg_type: ClassVar[str] = "processing"
    function_name: ClassVar[str] = "processing_default"  # type: ignore


def format_string_param(name: str, value: str) -> str:
    return f", {name} => '{value}'"


def format_bool_param(name: str, value: bool) -> str:
    return f", {name} => {str(value).lower()}"


@dataclass
class CreateVectorizerParams:
    source_table: str | None
    embedding: OpenAIConfig | OllamaConfig | VoyageAIConfig | None = None
    chunking: (
        CharacterTextSplitterConfig | RecursiveCharacterTextSplitterConfig | None
    ) = None
    indexing: DiskANNIndexingConfig | HNSWIndexingConfig | NoIndexingConfig | None = (
        None
    )
    formatting: ChunkValueConfig | PythonTemplateConfig | None = None
    scheduling: TimescaleSchedulingConfig | NoSchedulingConfig | None = None
    processing: ProcessingConfig | None = None
    target_schema: str | None = None
    target_table: str | None = None
    view_schema: str | None = None
    view_name: str | None = None
    queue_schema: str | None = None
    queue_table: str | None = None
    grant_to: list[str] | None = None
    enqueue_existing: bool = True

    def to_sql(self) -> str:
        parts = ["SELECT ai.create_vectorizer(", f"'{self.source_table}'::regclass"]

        # Handle all config objects that implement to_sql_argument
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, SQLArgumentProvider):
                parts.append(value.to_sql_argument())

        # Handle string parameters
        string_fields = [
            "target_schema",
            "target_table",
            "view_schema",
            "view_name",
            "queue_schema",
            "queue_table",
        ]
        for field in string_fields:
            value = getattr(self, field)
            if value is not None:
                parts.append(format_string_param(field, value))

        if self.grant_to:
            grant_list = ", ".join(f"'{user}'" for user in self.grant_to)
            parts.append(f", grant_to => ai.grant_to({grant_list})")

        if not self.enqueue_existing:
            parts.append(format_bool_param("enqueue_existing", False))

        parts.append(")")
        return "\n".join(parts)
