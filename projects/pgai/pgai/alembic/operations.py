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
    SchedulingConfig, NoScheduling,
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


def _build_chunking_params(config: ChunkingConfig) -> str:
    """Build chunking configuration parameters."""
    params = [f"'{config.chunk_column}'"]
    if config.chunk_size is not None:
        params.append(f"chunk_size=>{config.chunk_size}")
    if config.chunk_overlap is not None:
        params.append(f"chunk_overlap=>{config.chunk_overlap}")
    if config.separator is not None:
        if isinstance(config.separator, list):
            sep_str = "array[" + ",".join(f"'{s}'" for s in config.separator) + "]"
        else:
            sep_str = f"array['{config.separator}']"
        params.append(f"separators=>{sep_str}")
    if config.is_separator_regex:
        params.append("is_separator_regex=>true")
    return f"ai.chunking_recursive_character_text_splitter({', '.join(params)})"

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
    parts = ["SELECT ai.create_vectorizer("]
    parts.append(f"'{operation.source_table}'::regclass")

    if operation.destination:
        parts.append(f", destination => '{operation.destination}'")
    if operation.embedding:
        parts.append(f", embedding => {_build_embedding_params(operation.embedding)}")
    if operation.chunking:
        parts.append(f", chunking => {_build_chunking_params(operation.chunking)}")
    if operation.indexing:
        if isinstance(operation.indexing, DiskANNIndexingConfig):
            parts.append(f", indexing => {_build_diskann_indexing_params(operation.indexing)}")
        else:
            parts.append(f", indexing => {_build_hnsw_indexing_params(operation.indexing)}")
    if operation.formatting_template:
        parts.append(f", formatting => ai.formatting_python_template('{operation.formatting_template}')")
    if operation.scheduling:
        parts.append(f", scheduling => {_build_scheduling_params(operation.scheduling)}")
    if operation.processing:
        parts.append(f", processing => {_build_processing_params(operation.processing)}")
    if operation.target_schema:
        parts.append(f", target_schema => '{operation.target_schema}'")
    if operation.target_table:
        parts.append(f", target_table => '{operation.target_table}'")
    if operation.view_schema:
        parts.append(f", view_schema => '{operation.view_schema}'")
    if operation.view_name:
        parts.append(f", view_name => '{operation.view_name}'")
    if operation.queue_schema:
        parts.append(f", queue_schema => '{operation.queue_schema}'")
    if operation.queue_table:
        parts.append(f", queue_table => '{operation.queue_table}'")
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
