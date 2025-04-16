from typing import Any

from alembic.operations import MigrateOperation, Operations
from sqlalchemy import text

from pgai.vectorizer.create_vectorizer import CreateVectorizer


class CreateVectorizerOp(MigrateOperation):
    def __init__(
        self,
        **kw: dict[str, Any],
    ):
        self.params = CreateVectorizer(
            **kw  # type: ignore
        )

    @classmethod
    def create_vectorizer(cls, operations: Operations, **kw: Any):
        op = CreateVectorizerOp(**kw)  # type: ignore
        return operations.invoke(op)


class DropVectorizerOp(MigrateOperation):
    def __init__(self, vectorizer_id: int | None, drop_all: bool):
        self.vectorizer_id = vectorizer_id
        self.drop_all = drop_all

    @classmethod
    def drop_vectorizer(
        cls,
        operations: Operations,
        vectorizer_id: int | None,
        drop_all: bool = True,
    ):
        op = DropVectorizerOp(vectorizer_id, drop_all)
        return operations.invoke(op)


def create_vectorizer(operations: Operations, operation: CreateVectorizerOp):
    params = operation.params
    operations.execute(params.to_sql())


def drop_vectorizer(operations: Operations, operation: DropVectorizerOp):
    connection = operations.get_bind()
    # Drop the vectorizer
    connection.execute(
        text("SELECT ai.drop_vectorizer(:id, drop_all=>:drop_all)"),
        {"id": operation.vectorizer_id, "drop_all": operation.drop_all},
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
