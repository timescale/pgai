import re
from dataclasses import dataclass, fields
from typing import ClassVar, Protocol, runtime_checkable

from pgai.vectorizer.base import (
    BaseDiskANNIndexing,
    BaseHNSWIndexing,
    BaseOllamaConfig,
    BaseOpenAIConfig,
    BaseProcessing,
    BasePythonTemplate,
    BaseTimescaleScheduling,
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


def format_sql_params(params: dict[str, str | None | bool]) -> str:
    """Format dictionary of parameters into SQL argument string without any quoting."""
    formatted: list[str] = []
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            formatted.append(f"{key}=>{str(value).lower()}")
        else:
            formatted.append(f"{key}=>{value}")
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
                    if isinstance(value, str):
                        # Use E string syntax to handle any special
                        # characters in strings
                        value = f"E'{value}'"
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


class DiskANNIndexingConfig(BaseDiskANNIndexing, SQLArgumentMixin):
    arg_type: ClassVar[str] = "indexing"


class HNSWIndexingConfig(BaseHNSWIndexing, SQLArgumentMixin):
    arg_type: ClassVar[str] = "indexing"


class NoSchedulingConfig:
    arg_type: ClassVar[str] = "scheduling"

    def to_sql_argument(self) -> str:
        return f", {self.arg_type: ClassVar[str]} => ai.scheduling_none()"


class TimescaleSchedulingConfig(BaseTimescaleScheduling, SQLArgumentMixin):
    arg_type: ClassVar[str] = "scheduling"


class ProcessingConfig(BaseProcessing, SQLArgumentMixin):
    arg_type: ClassVar[str] = "processing"


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
