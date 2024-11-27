import textwrap
from dataclasses import dataclass, fields
from typing import Any, Literal, Protocol, runtime_checkable

from alembic.autogenerate.api import AutogenContext
from typing_extensions import override

from pgai.vectorizer.chunking import (
    LangChainCharacterTextSplitter,
    LangChainRecursiveCharacterTextSplitter,
)
from pgai.vectorizer.embeddings import OpenAI
from pgai.vectorizer.processing import ProcessingDefault


def equivalent_value(a: Any, b: Any, default: Any) -> bool:
    """Compare two values considering a default value as equivalent to None."""
    return (a == b) or (a is None and b == default) or (b is None and a == default)


def equivalent_dataclass_with_defaults(
    a: Any, b: Any, defaults: dict[str, Any], ignored_fields: tuple[str, ...] = ()
) -> bool:
    """
    Compare two dataclass instances considering default values as equivalent to None.

    Args:
        a: First dataclass instance
        b: Second dataclass instance
        defaults: Dictionary mapping field names to their default values
    """
    if type(a) is not type(b):
        return False

    for field in fields(a):
        if field.name in ignored_fields:
            continue
        a_val = getattr(a, field.name)
        b_val = getattr(b, field.name)
        default = defaults.get(field.name)

        if default is not None:
            if not equivalent_value(a_val, b_val, default):
                return False
        else:
            if a_val != b_val:
                return False

    return True


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
class EmbeddingConfig:
    model: str
    dimensions: int
    chat_user: str | None = None
    api_key_name: str | None = None

    _defaults = {"dimensions": 1536, "api_key_name": "OPENAI_API_KEY"}

    @override
    def __eq__(self, other: object) -> bool:
        return equivalent_dataclass_with_defaults(self, other, self._defaults)

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

    @classmethod
    def from_db_config(cls, openai_config: OpenAI) -> "EmbeddingConfig":
        return cls(
            model=openai_config.model,
            dimensions=openai_config.dimensions or 1536,
            chat_user=openai_config.user,
            api_key_name=openai_config.api_key_name,
        )


@dataclass
class ChunkingConfig:
    chunk_column: str
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    separator: list[str] | str | None = None
    is_separator_regex: bool = False

    _defaults = {
        "chunk_size": 800,
        "chunk_overlap": 400,
        "is_separator_regex": False,
        "separator": ["\n\n", "\n", ".", "?", "!", " ", ""],
    }

    @override
    def __eq__(self, other: object) -> bool:
        return equivalent_dataclass_with_defaults(self, other, self._defaults)

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

    @classmethod
    def from_db_config(
        cls,
        config: LangChainCharacterTextSplitter
        | LangChainRecursiveCharacterTextSplitter,
    ) -> "ChunkingConfig":
        if isinstance(config, LangChainCharacterTextSplitter):
            return cls(
                chunk_column=config.chunk_column,
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
                separator=config.separator,
                is_separator_regex=config.is_separator_regex,
            )
        else:
            return cls(
                chunk_column=config.chunk_column,
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
                separator=config.separators,
                is_separator_regex=config.is_separator_regex,
            )


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

    _defaults = {"min_rows": 100000, "create_when_queue_empty": True}

    @override
    def __eq__(self, other: object) -> bool:
        return equivalent_dataclass_with_defaults(self, other, self._defaults)

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
    opclass: Literal["vector_cosine_ops", "vector_l2_ops", "vector_ip_ops"] | None = (
        None
    )
    m: int | None = None
    ef_construction: int | None = None
    create_when_queue_empty: bool | None = None

    _defaults = {
        "min_rows": 100000,
        "opclass": "vector_cosine_ops",
        "create_when_queue_empty": True,
    }

    @override
    def __eq__(self, other: object) -> bool:
        return equivalent_dataclass_with_defaults(self, other, self._defaults)

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
class NoScheduling:
    @override
    def __eq__(self, other: object) -> bool:
        return isinstance(other, NoScheduling)

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

    _defaults = {"schedule_interval": "5m", "fixed_schedule": False}

    @override
    def __eq__(self, other: object) -> bool:
        return equivalent_dataclass_with_defaults(self, other, self._defaults)

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

    _defaults = {"batch_size": 50, "concurrency": 1}

    def to_sql_argument(self) -> str:
        params: list[str] = []
        if self.batch_size is not None:
            params.append(f"batch_size=>{self.batch_size}")
        if self.concurrency is not None:
            params.append(f"concurrency=>{self.concurrency}")
        return f", processing => ai.processing_default({', '.join(params)})"

    def to_python_arg(self) -> str:
        return format_python_arg("processing", self)

    @override
    def __eq__(self, other: object) -> bool:
        return equivalent_dataclass_with_defaults(self, other, self._defaults)

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
    embedding: EmbeddingConfig | None = None
    chunking: ChunkingConfig | None = None
    indexing: DiskANNIndexingConfig | HNSWIndexingConfig | None = None
    formatting_template: str | None = None
    scheduling: SchedulingConfig | NoScheduling | None = None
    processing: ProcessingConfig | None = None
    target_schema: str | None = None
    target_table: str | None = None
    view_schema: str | None = None
    view_name: str | None = None
    queue_schema: str | None = None
    queue_table: str | None = None
    grant_to: list[str] | None = None
    enqueue_existing: bool = True

    _defaults = {
        "formatting_template": "$chunk",
        "enqueue_existing": True,
        "processing": ProcessingConfig(),
        "scheduling": NoScheduling(),
        "queue_schema": "ai",
    }

    # The queue table name is autogenerated
    # and there is no reasonable way to determine it as a default value
    ignored_fields = ("queue_table",)

    @override
    def __eq__(self, other: object) -> bool:
        return equivalent_dataclass_with_defaults(
            self, other, self._defaults, self.ignored_fields
        )

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

    @classmethod
    def from_db_config(cls, row: dict[str, Any]) -> "CreateVectorizerParams":
        """
        Creates CreateVectorizerParams from database configuration.

        Args:
            row: A dictionary containing the vectorizer configuration from database,
                including 'config' field with complete JSON configuration

        Returns:
            CreateVectorizerParams: A new instance configured from database settings
        """
        config = row["config"]
        if not isinstance(config, dict):
            raise ValueError("Config must be a dictionary")

        # Parse embedding config
        embedding_config = None
        if embed_cfg := config.get("embedding"):  # type: ignore
            if not isinstance(embed_cfg, dict):
                raise ValueError("Embedding config must be a dictionary")
            embedding_config = EmbeddingConfig.from_db_config(OpenAI(**embed_cfg))  # type: ignore

        # Parse chunking config
        chunking_config = None
        if chunk_cfg := config.get("chunking"):  # type: ignore
            if not isinstance(chunk_cfg, dict):
                raise ValueError("Chunking config must be a dictionary")
            if chunk_cfg["implementation"] == "character_text_splitter":
                chunking_config = ChunkingConfig.from_db_config(
                    LangChainCharacterTextSplitter(**chunk_cfg)  # type: ignore
                )
            else:
                chunking_config = ChunkingConfig.from_db_config(
                    LangChainRecursiveCharacterTextSplitter(**chunk_cfg)  # type: ignore
                )

        # Parse processing config
        processing_config = None
        if proc_cfg := config.get("processing"):  # type: ignore
            if not isinstance(proc_cfg, dict):
                raise ValueError("Processing config must be a dictionary")
            processing_config = ProcessingConfig.from_db_config(
                ProcessingDefault(**proc_cfg)  # type: ignore
            )

        # Parse indexing config
        indexing_config = None
        if idx_cfg := config.get("indexing"):  # type: ignore
            if not isinstance(idx_cfg, dict):
                raise ValueError("Indexing config must be a dictionary")
            if idx_cfg.get("implementation") == "diskann":  # type: ignore
                indexing_config = DiskANNIndexingConfig(
                    min_rows=idx_cfg.get("min_rows"),  # type: ignore
                    storage_layout=idx_cfg.get("storage_layout"),  # type: ignore
                    num_neighbors=idx_cfg.get("num_neighbors"),  # type: ignore
                    search_list_size=idx_cfg.get("search_list_size"),  # type: ignore
                    max_alpha=idx_cfg.get("max_alpha"),  # type: ignore
                    num_dimensions=idx_cfg.get("num_dimensions"),  # type: ignore
                    num_bits_per_dimension=idx_cfg.get("num_bits_per_dimension"),  # type: ignore
                    create_when_queue_empty=idx_cfg.get("create_when_queue_empty"),  # type: ignore
                )
            elif idx_cfg.get("implementation") == "hnsw":  # type: ignore
                indexing_config = HNSWIndexingConfig(
                    min_rows=idx_cfg.get("min_rows"),  # type: ignore
                    opclass=idx_cfg.get("opclass"),  # type: ignore
                    m=idx_cfg.get("m"),  # type: ignore
                    ef_construction=idx_cfg.get("ef_construction"),  # type: ignore
                    create_when_queue_empty=idx_cfg.get("create_when_queue_empty"),  # type: ignore
                )

        # Parse scheduling config
        scheduling_config = None
        if sched_cfg := config.get("scheduling"):  # type: ignore
            if not isinstance(sched_cfg, dict):
                raise ValueError("Scheduling config must be a dictionary")
            if sched_cfg.get("implementation") == "none":  # type: ignore
                scheduling_config = NoScheduling()
            else:
                scheduling_config = SchedulingConfig(
                    schedule_interval=sched_cfg.get("schedule_interval"),  # type: ignore
                    initial_start=sched_cfg.get("initial_start"),  # type: ignore
                    fixed_schedule=sched_cfg.get("fixed_schedule"),  # type: ignore
                    timezone=sched_cfg.get("timezone"),  # type: ignore
                )

        # Get formatting template
        formatting_template = None
        if fmt_cfg := config.get("formatting"):  # type: ignore
            if not isinstance(fmt_cfg, dict):
                raise ValueError("Formatting config must be a dictionary")
            formatting_template = fmt_cfg.get("template")  # type: ignore

        return cls(
            source_table=row["source_table"],
            target_schema=row["target_schema"],
            target_table=row["target_table"],
            view_schema=row["view_schema"],
            view_name=row["view_name"],
            queue_schema=row["queue_schema"],
            queue_table=row["queue_table"],
            embedding=embedding_config,
            chunking=chunking_config,
            indexing=indexing_config,
            formatting_template=formatting_template,  # type: ignore
            scheduling=scheduling_config,
            processing=processing_config,
        )
