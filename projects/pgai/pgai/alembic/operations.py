from typing import Any

from alembic.operations import MigrateOperation, Operations
from sqlalchemy import text
from typing_extensions import override

from pgai.configuration import (
    ChunkingConfig,
    CreateVectorizerParams,
    DiskANNIndexingConfig,
    HNSWIndexingConfig,
    NoSchedulingConfig,
    OpenAIEmbeddingConfig,
    ProcessingConfig,
    SchedulingConfig,
)


@Operations.register_operation("create_vectorizer")
class CreateVectorizerOp(MigrateOperation):
    """Create a vectorizer for automatic embedding generation."""

    def __init__(
        self,
        source_table: str | None = None,
        embedding: OpenAIEmbeddingConfig | None = None,
        chunking: ChunkingConfig | None = None,
        indexing: DiskANNIndexingConfig | HNSWIndexingConfig | None = None,
        formatting_template: str | None = None,
        scheduling: SchedulingConfig | NoSchedulingConfig | None = None,
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
        self.params = CreateVectorizerParams(
            source_table=source_table,
            embedding=embedding,
            chunking=chunking,
            indexing=indexing,
            formatting_template=formatting_template,
            scheduling=scheduling,
            processing=processing,
            target_schema=target_schema,
            target_table=target_table,
            view_schema=view_schema,
            view_name=view_name,
            queue_schema=queue_schema,
            queue_table=queue_table,
            grant_to=grant_to,
            enqueue_existing=enqueue_existing,
        )

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


@Operations.implementation_for(CreateVectorizerOp)
def create_vectorizer(operations: Operations, operation: CreateVectorizerOp):
    """Implement CREATE VECTORIZER."""
    params = operation.params
    operations.execute(params.to_sql())


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
