from typing import Any

from alembic.operations import MigrateOperation, Operations
from sqlalchemy import text

from pgai.alembic.configuration import (
    CharacterTextSplitterConfig,
    ChunkValueConfig,
    CreateVectorizerParams,
    DiskANNIndexingConfig,
    HNSWIndexingConfig,
    NoIndexingConfig,
    NoSchedulingConfig,
    OllamaConfig,
    OpenAIConfig,
    ProcessingConfig,
    PythonTemplateConfig,
    RecursiveCharacterTextSplitterConfig,
    TimescaleSchedulingConfig,
    VoyageAIConfig,
)


class CreateVectorizerOp(MigrateOperation):
    def __init__(
        self,
        source_table: str | None,
        embedding: OpenAIConfig | OllamaConfig | VoyageAIConfig | None = None,
        chunking: CharacterTextSplitterConfig
        | RecursiveCharacterTextSplitterConfig
        | None = None,
        indexing: DiskANNIndexingConfig
        | HNSWIndexingConfig
        | NoIndexingConfig
        | None = None,
        formatting: ChunkValueConfig | PythonTemplateConfig | None = None,
        scheduling: TimescaleSchedulingConfig | NoSchedulingConfig | None = None,
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
            formatting=formatting,
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
        op = CreateVectorizerOp(source_table, **kw)
        return operations.invoke(op)


class DropVectorizerOp(MigrateOperation):
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
        op = DropVectorizerOp(vectorizer_id, drop_all)
        return operations.invoke(op)


def create_vectorizer(operations: Operations, operation: CreateVectorizerOp):
    params = operation.params
    operations.execute(params.to_sql())


def drop_vectorizer(operations: Operations, operation: DropVectorizerOp):
    connection = operations.get_bind()
    vectorizer_id = operation.vectorizer_id
    connection.execute(
        text("SELECT ai.drop_vectorizer(:id, drop_all=>:drop_all)"),
        {"id": vectorizer_id, "drop_all": operation.drop_all},
    )


_operations_registered = False


def register_operations():
    global _operations_registered

    if not _operations_registered:
        Operations.register_operation("create_vectorizer")(CreateVectorizerOp)
        Operations.register_operation("drop_vectorizer")(DropVectorizerOp)
        Operations.implementation_for(CreateVectorizerOp)(create_vectorizer)
        Operations.implementation_for(DropVectorizerOp)(drop_vectorizer)
        _operations_registered = True
