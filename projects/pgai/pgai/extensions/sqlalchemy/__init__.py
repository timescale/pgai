import sys
from typing import Any, Optional, Type

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import DeclarativeBase, mapped_column, relationship, backref
from sqlalchemy.orm.decl_api import registry


class VectorizerField:
    def __init__(
            self,
            source_column: str,
            embedding_model: str,
            chunking: dict[str, Any],
            formatting_template: str | None = None
    ):
        self.source_column = source_column
        self.embedding_model = embedding_model
        self.chunking = chunking
        self.formatting_template = formatting_template or "$chunk"

    def create_embedding_class(self, owner: type[DeclarativeBase]) -> type[DeclarativeBase]:
        table_name = f"{owner.__tablename__}_embedding_store"
        class_name = f"{owner.__name__}Embedding"
        base = owner.__base__
        registry_instance = owner.registry

        class Embedding(base):
            registry = registry_instance
            __tablename__ = table_name

            id = mapped_column(Integer, ForeignKey(f"{owner.__tablename__}.id"))
            embedding_uuid = mapped_column(Text, primary_key=True)
            chunk = mapped_column(Text, nullable=False)
            embedding = mapped_column(Vector(1536), nullable=False)
            chunk_seq = mapped_column(Integer, nullable=False)

        Embedding.__name__ = class_name
        return Embedding

    def __get__(self, obj, objtype=None):
        """
        When accessed on class (BlogPost.content_embeddings) -> return Embedding class
        When accessed on instance (post.content_embeddings) -> return relationship data
        """
        if obj is None:  # Class access
            return self._embedding_class
        # Instance access - return relationship data through the relationship property
        return getattr(obj, f"_{self.name}_relation")

    def __set_name__(self, owner, name):
        self.owner = owner
        self.name = name
        # Create and store the embeddings class
        self._embedding_class = self.create_embedding_class(owner)

        # Set up bidirectional relationship
        relationship_instance = relationship(
            self._embedding_class,
            foreign_keys=[self._embedding_class.id],
            backref=backref("parent", lazy="select")
        )
        setattr(owner, f"_{name}_relation", relationship_instance)