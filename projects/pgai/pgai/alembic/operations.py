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
    SchedulingConfig, NoScheduling, CreateVectorizerParams,
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
        scheduling: SchedulingConfig | NoScheduling | None = None,
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
            destination=destination,
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



def _build_embedding_params(config: EmbeddingConfig) -> str:
    """Build embedding configuration parameters."""
    params = [
        f"'{config.model}'",
        str(config.dimensions),
    ]
    if config.chat_user:
        params.append(f"chat_user=>'{config.chat_user}'")
    if config.api_key_name:
        params.append(f"api_key_name=>'{config.api_key_name}'")
    return f"ai.embedding_openai({', '.join(params)})"


def _build_diskann_indexing_params(config: DiskANNIndexingConfig) -> str:
    """Build DiskANN indexing configuration parameters."""
    params = []
    if config.min_rows is not None:
        params.append(f"min_rows=>{config.min_rows}")
    if config.storage_layout is not None:
        params.append(f"storage_layout=>'{config.storage_layout}'")
    if config.num_neighbors is not None:
        params.append(f"num_neighbors=>{config.num_neighbors}")
    if config.search_list_size is not None:
        params.append(f"search_list_size=>{config.search_list_size}")
    if config.max_alpha is not None:
        params.append(f"max_alpha=>{config.max_alpha}")
    if config.num_dimensions is not None:
        params.append(f"num_dimensions=>{config.num_dimensions}")
    if config.num_bits_per_dimension is not None:
        params.append(f"num_bits_per_dimension=>{config.num_bits_per_dimension}")
    if config.create_when_queue_empty is not None:
        params.append(f"create_when_queue_empty=>{str(config.create_when_queue_empty).lower()}")
    return f"ai.indexing_diskann({', '.join(params)})"


def _build_hnsw_indexing_params(config: HNSWIndexingConfig) -> str:
    """Build HNSW indexing configuration parameters."""
    params = []
    if config.min_rows is not None:
        params.append(f"min_rows=>{config.min_rows}")
    if config.opclass is not None:
        params.append(f"opclass=>'{config.opclass}'")
    if config.m is not None:
        params.append(f"m=>{config.m}")
    if config.ef_construction is not None:
        params.append(f"ef_construction=>{config.ef_construction}")
    if config.create_when_queue_empty is not None:
        params.append(f"create_when_queue_empty=>{str(config.create_when_queue_empty).lower()}")
    return f"ai.indexing_hnsw({', '.join(params)})"


def _build_scheduling_params(config: SchedulingConfig | NoScheduling) -> str:
    """Build scheduling configuration parameters."""
    if isinstance(config, NoScheduling):
        return "ai.scheduling_none()"

    params = []
    if config.schedule_interval is not None:
        params.append(f"schedule_interval=>'{config.schedule_interval}'")
    if config.initial_start is not None:
        params.append(f"initial_start=>'{config.initial_start}'")
    if config.fixed_schedule is not None:
        params.append(f"fixed_schedule=>{str(config.fixed_schedule).lower()}")
    if config.timezone is not None:
        params.append(f"timezone=>'{config.timezone}'")
    return f"ai.scheduling_timescaledb({', '.join(params)})"


def _build_processing_params(config: ProcessingConfig) -> str:
    """Build processing configuration parameters."""
    params = []
    if config.batch_size is not None:
        params.append(f"batch_size=>{config.batch_size}")
    if config.concurrency is not None:
        params.append(f"concurrency=>{config.concurrency}")
    return f"ai.processing_default({', '.join(params)})"


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
