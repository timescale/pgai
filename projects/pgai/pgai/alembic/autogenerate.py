from dataclasses import dataclass, fields
from typing import Any

from alembic.autogenerate import comparators, renderers
from alembic.autogenerate.api import AutogenContext
from alembic.operations.ops import UpgradeOps
from sqlalchemy import text

from pgai.alembic.operations import CreateVectorizerOp, DropVectorizerOp
from pgai.configuration import (
    CreateVectorizerParams,
)


def extract_top_level_fields(dc: Any) -> dict[str, Any]:
    """Extract only top-level fields from a dataclass,
    preserving nested dataclass instances."""
    return {field.name: getattr(dc, field.name) for field in fields(dc)}


@dataclass
class ExistingVectorizer:
    id: int
    create_params: CreateVectorizerParams


@comparators.dispatch_for("schema")
def compare_vectorizers(
    autogen_context: AutogenContext, upgrade_ops: UpgradeOps, schemas: list[str]
):
    """Compare vectorizers between model and database,
    generating appropriate migration operations."""

    conn = autogen_context.connection
    metadata = autogen_context.metadata
    assert metadata is not None
    assert conn is not None

    # Get existing vectorizers with their full configuration from database
    existing_vectorizers: dict[str, ExistingVectorizer] = {}
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

            # Convert row to dict for from_db_config
            row_dict = {
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

            existing_vectorizer = ExistingVectorizer(
                row_dict["id"], CreateVectorizerParams.from_db_config(row_dict)
            )
            existing_vectorizers[target_table] = existing_vectorizer
    # Get vectorizers from models
    model_vectorizers: dict[str, CreateVectorizerParams] = {}
    if hasattr(metadata, "info"):
        vectorizers = metadata.info.get("vectorizers", {})
        for _key, params in vectorizers.items():
            assert isinstance(params, CreateVectorizerParams)
            source_schema = "public"
            target_table = params.target_table or ""
            if "." not in target_table:
                target_table = f"{source_schema}.{target_table}"
            model_vectorizers[target_table] = params

    # Compare and generate operations
    for table_name, model_config in model_vectorizers.items():
        if table_name not in existing_vectorizers:
            # Create new vectorizer
            upgrade_ops.ops.append(
                CreateVectorizerOp(**extract_top_level_fields(model_config))
            )
        else:
            # Check for configuration changes
            existing_config = existing_vectorizers[table_name]
            if _config_has_changed(model_config, existing_config.create_params):
                # Drop and recreate vectorizer if config changed
                upgrade_ops.ops.extend(
                    [
                        DropVectorizerOp(
                            existing_config.id,
                            drop_all=True,
                        ),
                        CreateVectorizerOp(**extract_top_level_fields(model_config)),
                    ]
                )

    for table_name, existing_config in existing_vectorizers.items():
        if table_name not in model_vectorizers:
            upgrade_ops.ops.append(
                DropVectorizerOp(
                    existing_config.id,
                    drop_all=True,
                )
            )


def _config_has_changed(
    model_config: CreateVectorizerParams, existing_config: CreateVectorizerParams
) -> bool:
    """Compare vectorizer configurations to detect changes.

    Returns True if any configuration parameters have changed.
    """
    return model_config != existing_config


@renderers.dispatch_for(CreateVectorizerOp)
def render_create_vectorizer(autogen_context: AutogenContext, op: CreateVectorizerOp):
    """Render a CREATE VECTORIZER operation."""
    # Track which config classes are actually used
    return op.params.to_python(autogen_context)


@renderers.dispatch_for(DropVectorizerOp)
def render_drop_vectorizer(autogen_context: AutogenContext, op: DropVectorizerOp):  # noqa: ARG001
    """Render a DROP VECTORIZER operation."""
    args: list[str] = []

    if op.vectorizer_id is not None:
        args.append(str(op.vectorizer_id))

    if op.drop_all:
        args.append(f"drop_all={op.drop_all}")

    return f"op.drop_vectorizer({', '.join(args)})"
