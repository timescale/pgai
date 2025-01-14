from typing import Any

from alembic.operations import MigrateOperation, Operations
from sqlalchemy import text

from pgai.alembic.vectorizer_params import CreateVectorizerParams


class CreateVectorizerOp(MigrateOperation):
    def __init__(
        self,
        **kw: dict[str, Any],
    ):
        self.params = CreateVectorizerParams(
            **kw  # type: ignore
        )

    @classmethod
    def create_vectorizer(cls, operations: Operations, **kw: Any):
        op = CreateVectorizerOp(**kw)  # type: ignore
        return operations.invoke(op)


class DropVectorizerOp(MigrateOperation):
    def __init__(self, table_name: str | None, drop_all: bool):
        self.table_name = table_name
        self.drop_all = drop_all

    @classmethod
    def drop_vectorizer(
        cls,
        operations: Operations,
        table_name: str | None,
        drop_all: bool = True,
    ):
        op = DropVectorizerOp(table_name, drop_all)
        return operations.invoke(op)


def create_vectorizer(operations: Operations, operation: CreateVectorizerOp):
    params = operation.params
    operations.execute(params.to_sql())


def drop_vectorizer(operations: Operations, operation: DropVectorizerOp):
    connection = operations.get_bind()
    result = connection.execute(
        text("SELECT id FROM ai.vectorizer WHERE target_table = :table_name"),
        {"table_name": operation.table_name},
    ).scalar()

    if result is None:
        print(f"No vectorizer found for table .{operation.table_name}")
        return

    print(f"Found vectorizer with ID: {result} for table {operation.table_name}")

    # Drop the vectorizer
    connection.execute(
        text("SELECT ai.drop_vectorizer(:id, drop_all=>:drop_all)"),
        {"id": result, "drop_all": operation.drop_all},
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
