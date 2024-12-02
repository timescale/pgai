from typing import Any, Generic, TypeVar

from pgvector.sqlalchemy import Vector  # type: ignore
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, backref, mapped_column, relationship

from pgai.configuration import (
    OpenAIEmbeddingConfig,
)

# Type variable for the parent model
T = TypeVar("T", bound=DeclarativeBase)


def to_pascal_case(text: str):
    # Split on any non-alphanumeric character
    words = "".join(char if char.isalnum() else " " for char in text).split()

    # Capitalize first letter of all words
    return "".join(word.capitalize() for word in words)


class EmbeddingModel(DeclarativeBase, Generic[T]):
    """Base type for embedding models with required attributes"""

    embedding_uuid: Mapped[str]
    id: Mapped[int]
    chunk: Mapped[str]
    embedding: Mapped[list[float]]
    chunk_seq: Mapped[int]
    parent: T  # Type of the parent model


class VectorizerField:
    def __init__(
        self,
        embedding: OpenAIEmbeddingConfig,
        target_schema: str | None = None,
        target_table: str | None = None,
        add_relationship: bool = False,
    ):
        self.add_relationship = add_relationship
        self.embedding_config = embedding

        # Store table/view configuration
        self.target_schema = target_schema
        self.target_table = target_table
        self.owner: type[DeclarativeBase] | None = None
        self.name: str | None = None

    def set_schemas_correctly(self, owner: type[T]) -> None:
        table_args_schema_name = getattr(owner, "__table_args__", {}).get("schema")
        self.target_schema = (
            self.target_schema
            or table_args_schema_name
            or owner.registry.metadata.schema
            or "public"
        )

    def create_embedding_class(
        self, owner: type[T], name: str
    ) -> type[EmbeddingModel[T]]:
        table_name = self.target_table or f"{owner.__tablename__}_{name}_store"
        self.set_schemas_correctly(owner)
        class_name = f"{to_pascal_case(name)}Embedding"
        registry_instance = owner.registry
        base: type[DeclarativeBase] = owner.__base__  # type: ignore

        class Embedding(base):
            __tablename__ = table_name
            __table_args__ = (
                {"info": {"pgai_managed": True}, "schema": self.target_schema}
                if self.target_schema
                and self.target_schema != owner.registry.metadata.schema
                else {"info": {"pgai_managed": True}}
            )
            registry = registry_instance

            embedding_uuid = mapped_column(Text, primary_key=True)
            id = mapped_column(
                Integer, ForeignKey(f"{owner.__tablename__}.id", ondelete="CASCADE")
            )
            chunk = mapped_column(Text, nullable=False)
            embedding = mapped_column(
                Vector(self.embedding_config.dimensions), nullable=False
            )
            chunk_seq = mapped_column(Integer, nullable=False)

        Embedding.__name__ = class_name
        return Embedding  # type: ignore

    def __get__(
        self, obj: DeclarativeBase | None, objtype: type[DeclarativeBase] | None = None
    ) -> type[EmbeddingModel[Any]]:
        return self._embedding_class

    def __set_name__(self, owner: type[DeclarativeBase], name: str):
        self.owner = owner
        self.name = name
        self._embedding_class = self.create_embedding_class(owner, name)

        # Set up relationship
        if self.add_relationship:
            relationship_instance = relationship(
                self._embedding_class,
                foreign_keys=[self._embedding_class.id],
                backref=backref("parent", lazy="select"),
            )
            setattr(owner, f"{name}_relation", relationship_instance)
