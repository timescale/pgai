from typing import Any

from alembic.autogenerate import renderers
from alembic.autogenerate.api import AutogenContext
from alembic.operations import MigrateOperation, Operations
from sqlalchemy import text
from typing_extensions import override

from pgai.configuration import (
    ChunkingConfig,
    DiskANNIndexingConfig,
    EmbeddingConfig,
    HNSWIndexingConfig,
    ProcessingConfig,
    SchedulingConfig,
)


@Operations.register_operation("create_vectorizer")
class CreateVectorizerOp(MigrateOperation):
    """Create a vectorizer for automatic embedding generation."""

    def __init__(
        self,
        source_table: str | None = None,
        destination: str | None = None,
        embedding: EmbeddingConfig | None = None,
        chunking: ChunkingConfig | None = None,
        indexing: DiskANNIndexingConfig | HNSWIndexingConfig | None = None,
        formatting_template: str | None = None,
        scheduling: SchedulingConfig | None = None,
        processing: ProcessingConfig | None = None,
        target_schema: str | None = None,
        target_table: str | None = None,
        view_schema: str | None = None,
        view_name: str | None = None,
        queue_schema: str | None = None,
        queue_table: str | None = None,
        grant_to: list[str] | None = None,
        enqueue_existing: bool = True,
    ):
        self.source_table = source_table
        self.destination = destination
        self.embedding = embedding
        self.chunking = chunking
        self.indexing = indexing
        self.formatting_template = formatting_template
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
    def create_vectorizer(cls, operations: Operations, source_table: str, **kw: Any):
        """Issue a CREATE VECTORIZER command."""
        op = CreateVectorizerOp(source_table, **kw)
        return operations.invoke(op)

    @override
    def reverse(self) -> MigrateOperation:
        """Creates the downgrade operation"""
        return DropVectorizerOp(None, True)


@Operations.register_operation("drop_vectorizer")
class DropVectorizerOp(MigrateOperation):
    """Drop a vectorizer and its associated objects."""

    def __init__(self, vectorizer_id: int | None, drop_all: bool):
        self.vectorizer_id = vectorizer_id
        self.drop_all = drop_all

    @classmethod
    def drop_vectorizer(
        cls,
        operations: Operations,
        vectorizer_id: int | None = None,
        drop_all: bool = True,
    ):
        """Issue a DROP VECTORIZER command."""
        op = DropVectorizerOp(vectorizer_id, drop_all)
        return operations.invoke(op)

    @override
    def reverse(self) -> MigrateOperation:
        """Creates the upgrade operation"""
        return CreateVectorizerOp(None)


def _build_embedding_params(config: EmbeddingConfig) -> str:
    return (
        f"ai.embedding_openai('{config.model}', {config.dimensions}"
        + (f", chat_user=>'{config.chat_user}'" if config.chat_user else "")
        + (f", api_key_name=>'{config.api_key_name}'" if config.api_key_name else "")
        + ")"
    )


def _build_chunking_params(config: ChunkingConfig) -> str:
    base = f"ai.chunking_character_text_splitter('{config.chunk_column}'"
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
def create_vectorizer(operations: Operations, operation: CreateVectorizerOp):
    """Implement CREATE VECTORIZER."""

    parts = ["SELECT ai.create_vectorizer("]
    parts.append(f"'{operation.source_table}'::regclass")

    if operation.destination:
        parts.append(f", destination => '{operation.destination}'")

    if operation.embedding:
        parts.append(f", embedding => {_build_embedding_params(operation.embedding)}")

    if operation.chunking:
        parts.append(f", chunking => {_build_chunking_params(operation.chunking)}")

    parts.append(
        f", formatting => ai.formatting_python_template('{operation.formatting_template}')"  # noqa: E501
    )

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

    # Finally drop the vectorizer itself
    connection.execute(
        text("SELECT ai.drop_vectorizer(:id, drop_all=>:drop_all)"),
        {"id": vectorizer_id, "drop_all": operation.drop_all},
    )
