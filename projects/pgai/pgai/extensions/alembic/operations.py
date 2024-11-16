import json
from dataclasses import dataclass, asdict
from typing import Any

from alembic.autogenerate import renderers, comparators
from alembic.autogenerate.api import AutogenContext
from alembic.operations import MigrateOperation, Operations
from sqlalchemy import text
import alembic.context as AlembicContext


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
class IndexingConfig:
    min_rows: int | None = None
    storage_layout: str | None = None
    num_neighbors: int | None = None
    search_list_size: int | None = None
    max_alpha: float | None = None
    num_dimensions: int | None = None
    num_bits_per_dimension: int | None = None
    create_when_queue_empty: bool | None = None

@dataclass
class FormattingConfig:
    template: str

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

@Operations.register_operation("create_vectorizer")
class CreateVectorizerOp(MigrateOperation):
    """Create a vectorizer for automatic embedding generation."""

    def __init__(
            self,
            source_table: str | None = None,
            destination: str | None = None,
            embedding: EmbeddingConfig | None = None,
            chunking: ChunkingConfig | None = None,
            indexing: IndexingConfig | None = None,
            formatting: FormattingConfig | None = None,
            scheduling: SchedulingConfig | None = None,
            processing: ProcessingConfig | None = None,
            target_schema: str | None = None,
            target_table: str | None = None,
            view_schema: str | None = None,
            view_name: str | None = None,
            queue_schema: str | None = None,
            queue_table: str | None = None,
            grant_to: list[str] | None = None,
            enqueue_existing: bool = True
    ):
        self.source_table = source_table
        self.destination = destination
        self.embedding = embedding
        self.chunking = chunking
        self.indexing = indexing
        self.formatting = formatting
        self.scheduling = scheduling
        self.processing = processing
        self.target_schema = target_schema
        self.target_table = target_table
        self.view_schema = view_schema
        self.view_name = view_name
        self.queue_schema = queue_schema
        self.queue_table = queue_table
        self.grant_to = grant_to
        self.enqueue_existing = enqueue_existing

    @classmethod
    def create_vectorizer(cls, operations: Operations, source_table: str, **kw: dict[Any, Any]):
        """Issue a CREATE VECTORIZER command."""
        op = CreateVectorizerOp(source_table, **kw)
        return operations.invoke(op)

    def reverse(self):
        """Creates the downgrade operation"""
        return DropVectorizerOp(None, True)


@Operations.register_operation("drop_vectorizer")
class DropVectorizerOp(MigrateOperation):
    """Drop a vectorizer and its associated objects."""

    def __init__(self, vectorizer_id: int | None, drop_objects: bool):
        self.vectorizer_id = vectorizer_id
        self.drop_objects = drop_objects

    @classmethod
    def drop_vectorizer(cls, operations: Operations, vectorizer_id: int|None = None, drop_objects: bool = True):
        """Issue a DROP VECTORIZER command."""
        op = DropVectorizerOp(vectorizer_id, drop_objects)
        return operations.invoke(op)

    def reverse(self):
        """Creates the upgrade operation"""
        return CreateVectorizerOp(None)

def _build_embedding_params(config: EmbeddingConfig) -> str:
    return f"ai.embedding_openai('{config.model}', {config.dimensions}"  + \
        (f", chat_user=>'{config.chat_user}'" if config.chat_user else "") + \
        (f", api_key_name=>'{config.api_key_name}'" if config.api_key_name else "") + \
        ")"

def _build_chunking_params(config: ChunkingConfig) -> str:
    base = f"ai.chunking_recursive_character_text_splitter('{config.chunk_column}'"
    if config.chunk_size is not None:
        base += f", chunk_size=>{config.chunk_size}"
    if config.chunk_overlap is not None:
        base += f", chunk_overlap=>{config.chunk_overlap}"
    if config.separator is not None:
        if isinstance(config.separator, list):
            sep_str = "array[" + ",".join(f"'{s}'" for s in config.separator) + "]"
        else:
            sep_str = f"'{config.separator}'"
        base += f", separator=>{sep_str}"
    if config.is_separator_regex:
        base += ", is_separator_regex=>true"
    base += ")"
    return base

@Operations.implementation_for(CreateVectorizerOp)
def create_vectorizer(operations, operation):
    """Implement CREATE VECTORIZER."""

    parts = ["SELECT ai.create_vectorizer("]
    parts.append(f"'{operation.source_table}'::regclass")

    if operation.destination:
        parts.append(f", destination => '{operation.destination}'")

    if operation.embedding:
        parts.append(f", embedding => {_build_embedding_params(operation.embedding)}")

    if operation.chunking:
        parts.append(f", chunking => {_build_chunking_params(operation.chunking)}")

    if operation.formatting:
        parts.append(f", formatting => ai.formatting_python_template('{operation.formatting.template}')")

    if operation.grant_to:
        grant_list = ", ".join(f"'{user}'" for user in operation.grant_to)
        parts.append(f", grant_to => ai.grant_to({grant_list})")

    if not operation.enqueue_existing:
        parts.append(", enqueue_existing => false")

    parts.append(")")

    sql = "\n".join(parts)
    operations.execute(sql)


@Operations.implementation_for(DropVectorizerOp)
def drop_vectorizer(operations: Operations, operation: DropVectorizerOp):
    """Implement DROP VECTORIZER with cleanup of dependent objects."""
    connection = operations.get_bind()
    vectorizer_id = operation.vectorizer_id
    if operation.drop_objects:
        # First get vectorizer info
        result = connection.execute(
            text("""
                SELECT source_table, target_table AS embedding_store, v.view_name
                FROM ai.vectorizer v 
                WHERE id = :id
            """),
            {"id": vectorizer_id}
        ).fetchone()

        if result:
            # Drop the view first
            if result.view_name:
                connection.execute(
                    text(f"DROP VIEW IF EXISTS {result.view_name}")
                )

            # Drop the embedding store table
            if result.embedding_store:
                connection.execute(
                    text(f"DROP TABLE IF EXISTS {result.embedding_store}")
                )

    # Finally drop the vectorizer itself
    connection.execute(
        text("SELECT ai.drop_vectorizer(:id)"),
        {"id": vectorizer_id}
    )


from alembic.autogenerate import renderers


@renderers.dispatch_for(CreateVectorizerOp)
def render_create_vectorizer(autogen_context: AutogenContext, op: CreateVectorizerOp):
    """Render a CREATE VECTORIZER operation."""
    template_context = {
        "EmbeddingConfig": "from pgai.extensions.alembic.operations import EmbeddingConfig",
        "ChunkingConfig": "from pgai.extensions.alembic.operations import ChunkingConfig",
        "FormattingConfig": "from pgai.extensions.alembic.operations import FormattingConfig",
        "IndexingConfig": "from pgai.extensions.alembic.operations import IndexingConfig",
        "SchedulingConfig": "from pgai.extensions.alembic.operations import SchedulingConfig",
        "ProcessingConfig": "from pgai.extensions.alembic.operations import ProcessingConfig"
    }

    for import_str in template_context.values():
        autogen_context.imports.add(import_str)

    args = [repr(op.source_table)]

    if op.destination:
        args.append(f"destination={repr(op.destination)}")

    if op.embedding:
        embed_args = [
            f"    model={repr(op.embedding.model)}",
            f"    dimensions={op.embedding.dimensions}"
        ]
        if op.embedding.chat_user:
            embed_args.append(f"    chat_user={repr(op.embedding.chat_user)}")
        if op.embedding.api_key_name:
            embed_args.append(f"    api_key_name={repr(op.embedding.api_key_name)}")

        args.append(
            "embedding=EmbeddingConfig(\n" +
            ",\n".join(embed_args) +
            "\n)"
        )

    if op.chunking:
        chunk_args = [f"    chunk_column={repr(op.chunking.chunk_column)}"]
        if op.chunking.chunk_size is not None:
            chunk_args.append(f"    chunk_size={op.chunking.chunk_size}")
        if op.chunking.chunk_overlap is not None:
            chunk_args.append(f"    chunk_overlap={op.chunking.chunk_overlap}")
        if op.chunking.separator is not None:
            chunk_args.append(f"    separator={repr(op.chunking.separator)}")
        if op.chunking.is_separator_regex:
            chunk_args.append(f"    is_separator_regex=True")

        args.append(
            "chunking=ChunkingConfig(\n" +
            ",\n".join(chunk_args) +
            "\n)"
        )

    if op.indexing:
        index_args = []
        if op.indexing.min_rows is not None:
            index_args.append(f"    min_rows={op.indexing.min_rows}")
        if op.indexing.storage_layout is not None:
            index_args.append(f"    storage_layout={repr(op.indexing.storage_layout)}")
        if op.indexing.num_neighbors is not None:
            index_args.append(f"    num_neighbors={op.indexing.num_neighbors}")
        if op.indexing.search_list_size is not None:
            index_args.append(f"    search_list_size={op.indexing.search_list_size}")
        if op.indexing.max_alpha is not None:
            index_args.append(f"    max_alpha={op.indexing.max_alpha}")
        if op.indexing.num_dimensions is not None:
            index_args.append(f"    num_dimensions={op.indexing.num_dimensions}")
        if op.indexing.num_bits_per_dimension is not None:
            index_args.append(f"    num_bits_per_dimension={op.indexing.num_bits_per_dimension}")
        if op.indexing.create_when_queue_empty is not None:
            index_args.append(f"    create_when_queue_empty={op.indexing.create_when_queue_empty}")

        if index_args:
            args.append(
                "indexing=IndexingConfig(\n" +
                ",\n".join(index_args) +
                "\n)"
            )

    if op.formatting:
        args.append(f"formatting=FormattingConfig(template={repr(op.formatting.template)})")

    if op.scheduling:
        sched_args = []
        if op.scheduling.schedule_interval is not None:
            sched_args.append(f"    schedule_interval={repr(op.scheduling.schedule_interval)}")
        if op.scheduling.initial_start is not None:
            sched_args.append(f"    initial_start={repr(op.scheduling.initial_start)}")
        if op.scheduling.fixed_schedule is not None:
            sched_args.append(f"    fixed_schedule={op.scheduling.fixed_schedule}")
        if op.scheduling.timezone is not None:
            sched_args.append(f"    timezone={repr(op.scheduling.timezone)}")

        if sched_args:
            args.append(
                "scheduling=SchedulingConfig(\n" +
                ",\n".join(sched_args) +
                "\n)"
            )

    if op.processing:
        proc_args = []
        if op.processing.batch_size is not None:
            proc_args.append(f"    batch_size={op.processing.batch_size}")
        if op.processing.concurrency is not None:
            proc_args.append(f"    concurrency={op.processing.concurrency}")

        if proc_args:
            args.append(
                "processing=ProcessingConfig(\n" +
                ",\n".join(proc_args) +
                "\n)"
            )

    if op.target_schema:
        args.append(f"target_schema={repr(op.target_schema)}")
    if op.target_table:
        args.append(f"target_table={repr(op.target_table)}")
    if op.view_schema:
        args.append(f"view_schema={repr(op.view_schema)}")
    if op.view_name:
        args.append(f"view_name={repr(op.view_name)}")
    if op.queue_schema:
        args.append(f"queue_schema={repr(op.queue_schema)}")
    if op.queue_table:
        args.append(f"queue_table={repr(op.queue_table)}")

    if op.grant_to:
        args.append(f"grant_to=[{', '.join(repr(x) for x in op.grant_to)}]")

    if not op.enqueue_existing:
        args.append("enqueue_existing=False")

    return "op.create_vectorizer(\n    " + ",\n    ".join(args) + "\n)"


@renderers.dispatch_for(DropVectorizerOp)
def render_drop_vectorizer(autogen_context: AutogenContext, op: DropVectorizerOp):
    """Render a DROP VECTORIZER operation."""
    args = []

    if op.vectorizer_id is not None:
        args.append(str(op.vectorizer_id))

    if op.drop_objects:
        args.append(f"drop_objects={op.drop_objects}")

    return f"op.drop_vectorizer({', '.join(args)})"

