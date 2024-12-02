import textwrap
from dataclasses import dataclass, fields
from typing import Any, Literal, Protocol, runtime_checkable

from alembic.autogenerate.api import AutogenContext
from pgai.vectorizer.processing import ProcessingDefault


@runtime_checkable
class SQLArgumentProvider(Protocol):
    def to_sql_argument(self) -> str: ...


@runtime_checkable
class PythonArgProvider(Protocol):
    def to_python_arg(self) -> str: ...


def format_python_arg(config_type: str, instance: Any) -> str:
    """Generate a formatted Python argument string for a config object.
    If the instance has no fields, returns a simple constructor call."""
    obj_fields = fields(instance)
    if not obj_fields:
        return f"{config_type}={type(instance).__name__}()"

    formatted_fields = textwrap.indent(
        ",\n".join(
            f"{field.name}={repr(getattr(instance, field.name))}"
            for field in obj_fields
            if getattr(instance, field.name) is not None
        ),
        "    ",
    )
    return f"{config_type}={type(instance).__name__}(\n{formatted_fields}\n)"


@dataclass
class OpenAIEmbeddingConfig:
    model: str
    dimensions: int
    chat_user: str | None = None
    api_key_name: str | None = None

    def to_sql_argument(self) -> str:
        params = [
            f"'{self.model}'",
            str(self.dimensions),
        ]
        if self.chat_user:
            params.append(f"chat_user=>'{self.chat_user}'")
        if self.api_key_name:
            params.append(f"api_key_name=>'{self.api_key_name}'")
        return f", embedding => ai.embedding_openai({', '.join(params)})"

    def to_python_arg(self) -> str:
        return format_python_arg("embedding", self)


@dataclass
class OllamaEmbeddingConfig:
    model: str
    dimensions: int
    base_url: str | None = None
    truncate: bool | None = None
    keep_alive: str | None = None

    def to_sql_argument(self) -> str:
        params = [
            f"'{self.model}'",
            str(self.dimensions),
        ]
        if self.base_url:
            params.append(f"base_url=>'{self.base_url}'")
        if self.truncate is False:
            params.append("truncate=>false")
        if self.keep_alive:
            params.append(f"keep_alive=>'{self.keep_alive}'")
        return f", embedding => ai.embedding_ollama({', '.join(params)})"

    def to_python_arg(self) -> str:
        return format_python_arg("embedding", self)


@dataclass
class ChunkingConfig:
    chunk_column: str
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    separator: list[str] | str | None = None
    is_separator_regex: bool = False

    def to_sql_argument(self) -> str:
        """Convert the chunking configuration to a SQL function call argument."""
        params = [f"'{self.chunk_column}'"]

        if self.chunk_size is not None:
            params.append(f"chunk_size=>{self.chunk_size}")

        if self.chunk_overlap is not None:
            params.append(f"chunk_overlap=>{self.chunk_overlap}")

        if self.separator is not None:
            if isinstance(self.separator, list):
                sep_str = "array[" + ",".join(f"'{s}'" for s in self.separator) + "]"
            else:
                sep_str = f"array['{self.separator}']"
            params.append(f"separators=>{sep_str}")

        if self.is_separator_regex:
            params.append("is_separator_regex=>true")

        return (
            f", chunking => "
            f"ai.chunking_recursive_character_text_splitter({', '.join(params)})"
        )

    def to_python_arg(self) -> str:
        return format_python_arg("chunking", self)


@dataclass
class NoIndexingConfig:

    def to_sql_argument(self) -> str:
        return ", indexing => ai.indexing_none()"

    def to_python_arg(self) -> str:
        return format_python_arg("indexing", self)



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


    def to_sql_argument(self) -> str:
        params: list[str] = []
        if self.min_rows is not None:
            params.append(f"min_rows=>{self.min_rows}")
        if self.storage_layout is not None:
            params.append(f"storage_layout=>'{self.storage_layout}'")
        if self.num_neighbors is not None:
            params.append(f"num_neighbors=>{self.num_neighbors}")
        if self.search_list_size is not None:
            params.append(f"search_list_size=>{self.search_list_size}")
        if self.max_alpha is not None:
            params.append(f"max_alpha=>{self.max_alpha}")
        if self.num_dimensions is not None:
            params.append(f"num_dimensions=>{self.num_dimensions}")
        if self.num_bits_per_dimension is not None:
            params.append(f"num_bits_per_dimension=>{self.num_bits_per_dimension}")
        if self.create_when_queue_empty is not None:
            params.append(
                f"create_when_queue_empty=>{str(self.create_when_queue_empty).lower()}"
            )
        return f", indexing => ai.indexing_diskann({', '.join(params)})"

    def to_python_arg(self) -> str:
        return format_python_arg("indexing", self)


@dataclass
class HNSWIndexingConfig:
    min_rows: int | None = None
    opclass: Literal["vector_cosine_ops", "vector_l1_ops", "vector_ip_ops"] | None = (
        None
    )
    m: int | None = None
    ef_construction: int | None = None
    create_when_queue_empty: bool | None = None



    def to_sql_argument(self) -> str:
        params: list[str] = []
        if self.min_rows is not None:
            params.append(f"min_rows=>{self.min_rows}")
        if self.opclass is not None:
            params.append(f"opclass=>'{self.opclass}'")
        if self.m is not None:
            params.append(f"m=>{self.m}")
        if self.ef_construction is not None:
            params.append(f"ef_construction=>{self.ef_construction}")
        if self.create_when_queue_empty is not None:
            params.append(
                f"create_when_queue_empty=>{str(self.create_when_queue_empty).lower()}"
            )
        return f", indexing => ai.indexing_hnsw({', '.join(params)})"

    def to_python_arg(self) -> str:
        return format_python_arg("indexing", self)


@dataclass
class NoSchedulingConfig:

    def to_sql_argument(self) -> str:
        return ", scheduling => ai.scheduling_none()"

    def to_python_arg(self) -> str:
        return format_python_arg("scheduling", self)



@dataclass
class SchedulingConfig:
    schedule_interval: str | None = None
    initial_start: str | None = None
    fixed_schedule: bool | None = None
    timezone: str | None = None


    def to_sql_argument(self) -> str:
        params: list[str] = []
        if self.schedule_interval is not None:
            params.append(f"schedule_interval=>'{self.schedule_interval}'")
        if self.initial_start is not None:
            params.append(f"initial_start=>'{self.initial_start}'")
        if self.fixed_schedule is not None:
            params.append(f"fixed_schedule=>{str(self.fixed_schedule).lower()}")
        if self.timezone is not None:
            params.append(f"timezone=>'{self.timezone}'")
        return f", scheduling => ai.scheduling_timescaledb({', '.join(params)})"

    def to_python_arg(self) -> str:
        return format_python_arg("scheduling", self)


@dataclass
class ProcessingConfig:
    batch_size: int | None = None
    concurrency: int | None = None


    def to_sql_argument(self) -> str:
        params: list[str] = []
        if self.batch_size is not None:
            params.append(f"batch_size=>{self.batch_size}")
        if self.concurrency is not None:
            params.append(f"concurrency=>{self.concurrency}")
        return f", processing => ai.processing_default({', '.join(params)})"

    def to_python_arg(self) -> str:
        return format_python_arg("processing", self)


    @classmethod
    def from_db_config(cls, config: ProcessingDefault) -> "ProcessingConfig":
        return cls(
            batch_size=config.batch_size,
            concurrency=config.concurrency,
        )


def format_string_param(name: str, value: str) -> str:
    return f", {name} => '{value}'"


def format_bool_param(name: str, value: bool) -> str:
    return f", {name} => {str(value).lower()}"


@dataclass
class CreateVectorizerParams:
    source_table: str | None
    embedding: OpenAIEmbeddingConfig | OllamaEmbeddingConfig | None = None
    chunking: ChunkingConfig | None = None
    indexing: DiskANNIndexingConfig | HNSWIndexingConfig | NoIndexingConfig | None = (
        None
    )
    formatting_template: str | None = None
    scheduling: SchedulingConfig | NoSchedulingConfig | None = None
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

        # Handle special cases
        if self.formatting_template is not None:
            parts.append(
                f", formatting => "
                f"ai.formatting_python_template('{self.formatting_template}')"
            )

        if self.grant_to:
            grant_list = ", ".join(f"'{user}'" for user in self.grant_to)
            parts.append(f", grant_to => ai.grant_to({grant_list})")

        if not self.enqueue_existing:
            parts.append(format_bool_param("enqueue_existing", False))

        parts.append(")")
        return "\n".join(parts)

    def to_python(self, autogen_context: AutogenContext) -> str:
        used_configs: set[str] = set()
        args = [repr(self.source_table)]

        # Handle all config objects that implement to_python_arg
        for field in fields(self):
            value = getattr(self, field.name)
            if isinstance(value, PythonArgProvider):
                args.append(value.to_python_arg())
                used_configs.add(type(value).__name__)

        # Handle string parameters
        string_fields = [
            "target_schema",
            "target_table",
            "view_schema",
            "view_name",
            "queue_schema",
            "queue_table",
            "formatting_template",
        ]
        for field in string_fields:
            value = getattr(self, field)
            if value is not None:
                args.append(f"{field}={repr(value)}")

        # Handle special cases
        if self.grant_to:
            args.append(f"grant_to=[{', '.join(repr(x) for x in self.grant_to)}]")
        if not self.enqueue_existing:
            args.append("enqueue_existing=False")

        # Generate single import line for used configs
        if used_configs:
            import_names = ", ".join(sorted(used_configs))
            autogen_context.imports.add(
                f"from pgai.configuration import {import_names}"
            )

        return "op.create_vectorizer(\n    " + ",\n    ".join(args) + "\n)"