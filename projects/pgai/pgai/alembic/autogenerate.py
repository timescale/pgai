from typing import Any

from alembic.autogenerate import comparators, renderers
from alembic.autogenerate.api import AutogenContext
from alembic.operations.ops import UpgradeOps
from sqlalchemy import text

from pgai.configuration import (
    ChunkingConfig,
    DiskANNIndexingConfig,
    EmbeddingConfig,
    ProcessingConfig,
    SchedulingConfig, NoScheduling,
)

from pgai.alembic.operations import CreateVectorizerOp, DropVectorizerOp


@comparators.dispatch_for("schema")
def compare_vectorizers(
    autogen_context: AutogenContext, upgrade_ops: UpgradeOps, schemas: list[str]
):
    """Compare vectorizers between model and database,
    generating appropriate migration operations.

    Handles creation, updates and deletion of vectorizers by comparing the
    current database state with the model definitions.
    """

    conn = autogen_context.connection
    metadata = autogen_context.metadata
    assert metadata is not None
    assert conn is not None

    # Get existing vectorizers with their full configuration from database
    existing_vectorizers: dict[str, dict[str, Any]] = {}
    for schema in schemas:
        result = conn.execute(
            text("""
            SELECT
                v.id,
                v.source_schema,
                v.source_table,
                v.target_schema,
                v.target_table,
                v.view_schema,
                v.view_name,
                v.queue_schema,
                v.queue_table,
                v.config
            FROM ai.vectorizer v
            WHERE v.source_schema = :schema
        """),
            {"schema": schema or "public"},
        ).fetchall()

        for row in result:
            source_schema = row.source_schema or "public"
            target_table = f"{row.target_schema or source_schema}.{row.target_table}"
            existing_vectorizers[target_table] = {
                "id": row.id,
                "source_schema": row.source_schema,
                "source_table": row.source_table,
                "target_schema": row.target_schema,
                "target_table": row.target_table,
                "view_schema": row.view_schema,
                "view_name": row.view_name,
                "queue_schema": row.queue_schema,
                "queue_table": row.queue_table,
                "config": row.config,
            }

    # Get vectorizers from models
    model_vectorizers: dict[str, dict[str, Any]] = {}
    if hasattr(metadata, "info"):
        vectorizers = metadata.info.get("vectorizers", {})
        for _key, config in vectorizers.items():
            source_schema = config.get("source_schema") or "public"
            target_table = config["target_table"]
            if "." not in target_table:
                target_table = f"{source_schema}.{target_table}"
            model_vectorizers[target_table] = config

    # Compare and generate operations
    for table_name, model_config in model_vectorizers.items():
        if table_name not in existing_vectorizers:
            # Create new vectorizer
            upgrade_ops.ops.append(
                _create_vectorizer_op(model_config)
            )
        else:
            # Check for configuration changes
            existing_config = existing_vectorizers[table_name]
            if _config_has_changed(model_config, existing_config):
                # Drop and recreate vectorizer if config changed
                upgrade_ops.ops.extend(
                    [
                        DropVectorizerOp(
                            existing_config["id"],
                            drop_all=True,
                        ),
                        _create_vectorizer_op(model_config),
                    ]
                )

    for table_name, existing_config in existing_vectorizers.items():
        if table_name not in model_vectorizers:
            upgrade_ops.ops.append(
                DropVectorizerOp(
                    existing_config["id"],
                    drop_all=True,
                )
            )


def _create_vectorizer_op(
        model_config: dict[str, Any]
) -> CreateVectorizerOp:
    return CreateVectorizerOp(
        source_table=model_config["source_table"],
        destination=model_config.get("destination"),
        embedding=EmbeddingConfig(**model_config["embedding"]),
        chunking=ChunkingConfig(**model_config["chunking"]),
        formatting_template=model_config.get(
            "formatting_template", "$chunk"
        ),
        indexing=DiskANNIndexingConfig(**model_config.get("indexing", {}))
        if "indexing" in model_config
        else None,
        scheduling=SchedulingConfig(**model_config.get("scheduling", {}))
        if "scheduling" in model_config
        else None,
        processing=ProcessingConfig(**model_config.get("processing", {}))
        if "processing" in model_config
        else None,
        target_schema=model_config.get("target_schema"),
        target_table=model_config.get("target_table"),
        view_schema=model_config.get("view_schema"),
        view_name=model_config.get("view_name"),
        queue_schema=model_config.get("queue_schema"),
        queue_table=model_config.get("queue_table"),
        grant_to=model_config.get("grant_to"),
        enqueue_existing=model_config.get("enqueue_existing", True),
    )
    

def _config_has_changed(
    model_config: dict[str, Any], existing_config: dict[str, Any]
) -> bool:
    """Compare vectorizer configurations to detect changes.

    Returns True if any configuration parameters have changed.
    """
    # Compare core components
    config_keys = {
        "embedding",
        "chunking",
        "formatting",
        "indexing",
        "scheduling",
        "processing",
    }
    for key in config_keys:
        model_value = model_config.get(key)
        existing_value = (
            existing_config["config"].get(key)
            if existing_config.get("config")
            else None
        )

        if model_value is None and existing_value is None:
            continue

        if model_value != existing_value:
            return True

    # Compare schema/table settings
    schema_keys = {
        "target_schema",
        "target_table",
        "view_schema",
        "view_name",
        "queue_schema",
        "queue_table",
    }

    for key in schema_keys:
        model_value = model_config.get(key)
        existing_value = existing_config.get(key)

        if model_value is None and existing_value is None:
            continue

        if model_value != existing_value:
            return True

    return False


@renderers.dispatch_for(CreateVectorizerOp)
def render_create_vectorizer(autogen_context: AutogenContext, op: CreateVectorizerOp):
    """Render a CREATE VECTORIZER operation."""
    # Track which config classes are actually used
    used_configs = set()

    args = [repr(op.source_table)]

    if op.destination:
        args.append(f"destination={repr(op.destination)}")

    if op.embedding:
        used_configs.add("EmbeddingConfig")
        embed_args = [
            f"    model={repr(op.embedding.model)}",
            f"    dimensions={op.embedding.dimensions}",
        ]
        if op.embedding.chat_user:
            embed_args.append(f"    chat_user={repr(op.embedding.chat_user)}")
        if op.embedding.api_key_name:
            embed_args.append(f"    api_key_name={repr(op.embedding.api_key_name)}")
        args.append("embedding=EmbeddingConfig(\n" + ",\n".join(embed_args) + "\n)")

    if op.chunking:
        used_configs.add("ChunkingConfig")
        chunk_args = [f"    chunk_column={repr(op.chunking.chunk_column)}"]
        if op.chunking.chunk_size is not None:
            chunk_args.append(f"    chunk_size={op.chunking.chunk_size}")
        if op.chunking.chunk_overlap is not None:
            chunk_args.append(f"    chunk_overlap={op.chunking.chunk_overlap}")
        if op.chunking.separator is not None:
            chunk_args.append(f"    separator={repr(op.chunking.separator)}")
        if op.chunking.is_separator_regex:
            chunk_args.append("    is_separator_regex=True")
        args.append("chunking=ChunkingConfig(\n" + ",\n".join(chunk_args) + "\n)")

    if op.indexing:
        if isinstance(op.indexing, DiskANNIndexingConfig):
            used_configs.add("DiskANNIndexingConfig")
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
                args.append("indexing=DiskANNIndexingConfig(\n" + ",\n".join(index_args) + "\n)")
        else:
            used_configs.add("HNSWIndexingConfig")
            index_args = []
            if op.indexing.min_rows is not None:
                index_args.append(f"    min_rows={op.indexing.min_rows}")
            if op.indexing.opclass is not None:
                index_args.append(f"    opclass={repr(op.indexing.opclass)}")
            if op.indexing.m is not None:
                index_args.append(f"    m={op.indexing.m}")
            if op.indexing.ef_construction is not None:
                index_args.append(f"    ef_construction={op.indexing.ef_construction}")
            if op.indexing.create_when_queue_empty is not None:
                index_args.append(f"    create_when_queue_empty={op.indexing.create_when_queue_empty}")
            if index_args:
                args.append("indexing=HNSWIndexingConfig(\n" + ",\n".join(index_args) + "\n)")

    if op.formatting_template:
        args.append(f"formatting_template={repr(op.formatting_template)}")

    if op.scheduling:
        if isinstance(op.scheduling, NoScheduling):
            used_configs.add("NoScheduling")
            args.append("scheduling=NoScheduling()")
        else:
            used_configs.add("SchedulingConfig")
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
                args.append("scheduling=SchedulingConfig(\n" + ",\n".join(sched_args) + "\n)")

    if op.processing:
        used_configs.add("ProcessingConfig")
        proc_args = []
        if op.processing.batch_size is not None:
            proc_args.append(f"    batch_size={op.processing.batch_size}")
        if op.processing.concurrency is not None:
            proc_args.append(f"    concurrency={op.processing.concurrency}")
        if proc_args:
            args.append("processing=ProcessingConfig(\n" + ",\n".join(proc_args) + "\n)")

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

    # Generate single import line for used configs
    if used_configs:
        import_names = ", ".join(sorted(used_configs))
        autogen_context.imports.add(f"from pgai.configuration import {import_names}")

    return "op.create_vectorizer(\n    " + ",\n    ".join(args) + "\n)"


@renderers.dispatch_for(DropVectorizerOp)
def render_drop_vectorizer(autogen_context: AutogenContext, op: DropVectorizerOp):  # noqa: ARG001
    """Render a DROP VECTORIZER operation."""
    args: list[str] = []

    if op.vectorizer_id is not None:
        args.append(str(op.vectorizer_id))

    if op.drop_all:
        args.append(f"drop_all={op.drop_all}")

    return f"op.drop_vectorizer({', '.join(args)})"
