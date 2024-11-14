from dataclasses import dataclass
from typing import Any

from alembic.autogenerate import renderers, comparators
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
    separator: str | list[str] | None = None
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
            source_table: str,
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
    def create_vectorizer(cls, operations, source_table: str, **kw):
        """Issue a CREATE VECTORIZER command."""
        op = CreateVectorizerOp(source_table, **kw)
        return operations.invoke(op)

    def reverse(self):
        return DropVectorizerOp(self.source_table)


@Operations.register_operation("drop_vectorizer")
class DropVectorizerOp(MigrateOperation):
    """Drop a vectorizer and its associated objects."""

    def __init__(self, vectorizer_id: int, drop_objects: bool = True):
        self.vectorizer_id = vectorizer_id
        self.drop_objects = drop_objects

    @classmethod
    def drop_vectorizer(cls, operations, vectorizer_id: int, drop_objects: bool = True):
        """Issue a DROP VECTORIZER command."""
        op = DropVectorizerOp(vectorizer_id, drop_objects)
        return operations.invoke(op)

def _build_embedding_json(config: EmbeddingConfig) -> str:
    return f"ai.embedding_openai('{config.model}', {config.dimensions}"  + \
        (f", chat_user=>'{config.chat_user}'" if config.chat_user else "") + \
        (f", api_key_name=>'{config.api_key_name}'" if config.api_key_name else "") + \
        ")"

def _build_chunking_json(config: ChunkingConfig) -> str:
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
        parts.append(f", embedding => {_build_embedding_json(operation.embedding)}")

    if operation.chunking:
        parts.append(f", chunking => {_build_chunking_json(operation.chunking)}")

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
def drop_vectorizer(operations, operation):
    """Implement DROP VECTORIZER with cleanup of dependent objects."""
    connection = operations.get_bind()

    if operation.drop_objects:
        # First get vectorizer info
        result = connection.execute(
            text("""
                SELECT source_table, target_table AS embedding_store, v.view_name
                FROM ai.vectorizer v 
                WHERE id = :id
            """),
            {"id": operation.vectorizer_id}
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
        {"id": operation.vectorizer_id}
    )


from alembic.autogenerate import renderers


@renderers.dispatch_for(CreateVectorizerOp)
def render_create_vectorizer(autogen_context, op):
    """Render a CREATE VECTORIZER operation."""
    template_context = {
        "EmbeddingConfig": "from pgai.extensions.alembic.operations import EmbeddingConfig",
        "ChunkingConfig": "from pgai.extensions.alembic.operations import ChunkingConfig",
        "FormattingConfig": "from pgai.extensions.alembic.operations import FormattingConfig",
    }
    autogen_context.imports.add(template_context["EmbeddingConfig"])
    autogen_context.imports.add(template_context["ChunkingConfig"])
    autogen_context.imports.add(template_context["FormattingConfig"])

    args = [repr(op.source_table)]

    if op.destination:
        args.append(f"destination={repr(op.destination)}")

    if op.embedding:
        embed_args = [
            f"    model={repr(op.embedding.model)}",
            f"    dimensions={op.embedding.dimensions}"
        ]
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

        args.append(
            "chunking=ChunkingConfig(\n" +
            ",\n".join(chunk_args) +
            "\n)"
        )

    if op.formatting:
        args.append(f"formatting=FormattingConfig(template={repr(op.formatting.template)})")

    if op.grant_to:
        args.append(f"grant_to=[{', '.join(repr(x) for x in op.grant_to)}]")

    if not op.enqueue_existing:
        args.append("enqueue_existing=False")

    return "op.create_vectorizer(\n    " + ",\n    ".join(args) + "\n)"


@renderers.dispatch_for(DropVectorizerOp)
def render_drop_vectorizer(autogen_context, op):
    """Render a DROP VECTORIZER operation."""
    return f"op.drop_vectorizer({op.vectorizer_id}, drop_objects={op.drop_objects})"

