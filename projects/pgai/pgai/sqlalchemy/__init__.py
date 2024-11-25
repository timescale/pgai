from dataclasses import asdict
from typing import Any, Generic, TypeVar

from pgvector.sqlalchemy import Vector  # type: ignore
from sqlalchemy import ForeignKey, Integer, MetaData, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, backref, mapped_column, relationship

from pgai.configuration import (
    ChunkingConfig,
    DiskANNIndexingConfig,
    EmbeddingConfig,
    HNSWIndexingConfig,
    NoScheduling,
    ProcessingConfig,
    SchedulingConfig,
)

# Type variable for the parent model
T = TypeVar("T", bound=DeclarativeBase)


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
        embedding: EmbeddingConfig,
        chunking: ChunkingConfig,
        formatting_template: str | None = None,
        indexing: DiskANNIndexingConfig | HNSWIndexingConfig | None = None,
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
        add_relationship: bool = False,
    ):
        self.add_relationship = add_relationship

        self.embedding_config = embedding

        self.chunking_config = chunking

        if formatting_template is None:
            self.formatting_template = "$chunk"
        else:
            self.formatting_template = formatting_template

        # Handle optional configs
        self.indexing_config = indexing

        self.scheduling_config = scheduling

        self.processing_config = processing

        # Store table/view configuration
        self.target_schema = target_schema
        self.target_table = target_table
        self.view_schema = view_schema
        self.view_name = view_name
        self.queue_schema = queue_schema
        self.queue_table = queue_table
        self.grant_to = grant_to
        self.enqueue_existing = enqueue_existing
        self.owner: type[DeclarativeBase] | None = None
        self.name: str | None = None

    def create_embedding_class(self, owner: type[T], name: str) -> type[EmbeddingModel[T]]:
        table_name = self.target_table or f"{owner.__tablename__}_{name}_store"
        schema = self.target_schema
        class_name = f"{owner.__name__}Embedding"
        registry_instance = owner.registry
        base: type[DeclarativeBase] = owner.__base__  # type: ignore

        class Embedding(base):
            __tablename__ = table_name
            __table_args__ = (
                {"info": {"pgai_managed": True}, "schema": schema}
                if schema
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
        if self.view_name is None:
            self.view_name = self.view_name or f"{owner.__tablename__}_{name}"

        # Set up relationship
        if self.add_relationship:
            relationship_instance = relationship(
                self._embedding_class,
                foreign_keys=[self._embedding_class.id],
                backref=backref("parent", lazy="select"),
            )
            setattr(owner, f"{name}_relation", relationship_instance)

        # Register vectorizer configuration

        metadata = owner.registry.metadata
        self._register_with_metadata(metadata)

    def _register_with_metadata(self, metadata: MetaData) -> None:
        """Register vectorizer configuration for migration generation"""
        if not hasattr(metadata, "info"):
            metadata.info = {}
        assert self.owner is not None

        vectorizers = metadata.info.setdefault("vectorizers", {})
        config = {
            "source_table": self.owner.__tablename__,
            "target_table": self._embedding_class.__tablename__,
            "embedding": asdict(self.embedding_config),
            "chunking": asdict(self.chunking_config),
            "formatting_template": self.formatting_template,
            "enqueue_existing": self.enqueue_existing,
        }

        # Add optional configurations if they exist
        if self.indexing_config:
            config["indexing"] = asdict(self.indexing_config)
        if self.scheduling_config:
            config["scheduling"] = asdict(self.scheduling_config)
        if self.processing_config:
            config["processing"] = asdict(self.processing_config)
        if self.target_schema:
            config["target_schema"] = self.target_schema
        if self.view_schema:
            config["view_schema"] = self.view_schema
        if self.view_name:
            config["view_name"] = self.view_name
        if self.queue_schema:
            config["queue_schema"] = self.queue_schema
        if self.queue_table:
            config["queue_table"] = self.queue_table
        if self.grant_to:
            config["grant_to"] = self.grant_to

        vectorizers[f"{self.owner.__tablename__}.{self.name}"] = config
