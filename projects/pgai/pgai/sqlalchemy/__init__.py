from typing import Any, Generic, TypeVar

from pgvector.sqlalchemy import Vector  # type: ignore
from sqlalchemy import ForeignKeyConstraint, Integer, MetaData, Text, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, backref, mapped_column, relationship

from pgai.configuration import (
    ChunkingConfig,
    CreateVectorizerParams,
    DiskANNIndexingConfig,
    HNSWIndexingConfig,
    NoSchedulingConfig,
    OpenAIEmbeddingConfig,
    ProcessingConfig,
    SchedulingConfig,
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
    chunk: Mapped[str]
    embedding: Mapped[Vector]
    chunk_seq: Mapped[int]
    parent: T  # Type of the parent model


class Vectorizer:
    def __init__(
        self,
        embedding: OpenAIEmbeddingConfig,
        chunking: ChunkingConfig,
        formatting_template: str | None = None,
        indexing: DiskANNIndexingConfig | HNSWIndexingConfig | None = None,
        scheduling: SchedulingConfig | NoSchedulingConfig | None = None,
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
        self.queue_schema = queue_schema or "ai"
        self.queue_table = queue_table
        self.grant_to = grant_to
        self.enqueue_existing = enqueue_existing
        self.owner: type[DeclarativeBase] | None = None
        self.name: str | None = None
        self._embedding_class: type[EmbeddingModel[Any]] | None = None
        self._initialized = False

    def _relationship_property(
        self, obj: Any = None
    ) -> Mapped[list[EmbeddingModel[Any]]]:
        # Force initialization if not done yet
        if not self._initialized:
            _ = self.__get__(obj, self.owner)
        # Return the actual relationship
        return getattr(obj, f"_{self.name}_relation")

    def set_schemas_correctly(self, owner: type[DeclarativeBase]) -> None:
        table_args_schema_name = getattr(owner, "__table_args__", {}).get("schema")
        self.target_schema = (
            self.target_schema
            or table_args_schema_name
            or owner.registry.metadata.schema
            or "public"
        )
        self.view_schema = self.view_schema or self.target_schema

    def create_embedding_class(
        self, owner: type[DeclarativeBase]
    ) -> type[EmbeddingModel[Any]]:
        assert self.name is not None
        class_name = f"{to_pascal_case(self.name)}Embedding"
        registry_instance = owner.registry
        base: type[DeclarativeBase] = owner.__base__  # type: ignore

        # Get primary key information from the fully initialized model
        mapper = inspect(owner)
        pk_cols = mapper.primary_key

        # Create the complete class dictionary
        class_dict: dict[str, Any] = {
            "__tablename__": self.target_table,
            "registry": registry_instance,
            # Add all standard columns
            "embedding_uuid": mapped_column(Text, primary_key=True),
            "chunk": mapped_column(Text, nullable=False),
            "embedding": mapped_column(
                Vector(self.embedding_config.dimensions), nullable=False
            ),
            "chunk_seq": mapped_column(Integer, nullable=False),
        }

        # Add primary key columns to the dictionary
        for col in pk_cols:
            class_dict[col.name] = mapped_column(col.type, nullable=False)

        # Create the table args with foreign key constraint
        table_args_dict: dict[str, Any] = dict()
        if self.target_schema and self.target_schema != owner.registry.metadata.schema:
            table_args_dict["schema"] = self.target_schema

        # Create the composite foreign key constraint
        fk_constraint = ForeignKeyConstraint(
            [col.name for col in pk_cols],  # Local columns
            [
                f"{owner.__tablename__}.{col.name}" for col in pk_cols
            ],  # Referenced columns
            ondelete="CASCADE",
        )

        # Add table args to class dictionary
        class_dict["__table_args__"] = (fk_constraint, table_args_dict)

        # Create the class using type()
        Embedding = type(class_name, (base,), class_dict)

        return Embedding  # type: ignore

    def __get__(
        self, obj: DeclarativeBase | None, objtype: type[DeclarativeBase] | None = None
    ) -> type[EmbeddingModel[Any]]:
        if not self._initialized and objtype is not None:
            self._embedding_class = self.create_embedding_class(objtype)

            # Set up relationship if requested
            if self.add_relationship:
                mapper = inspect(objtype)
                pk_cols = mapper.primary_key

                relationship_instance = relationship(
                    self._embedding_class,
                    foreign_keys=[
                        getattr(self._embedding_class, col.name) for col in pk_cols
                    ],
                    backref=backref("parent", lazy="select"),
                )
                # Store actual relationship under a private name
                setattr(objtype, f"_{self.name}_relation", relationship_instance)

            self._initialized = True

        if self._embedding_class is None:
            raise RuntimeError("Embedding class not properly initialized")

        return self._embedding_class

    def __set_name__(self, owner: type[DeclarativeBase], name: str):
        self.owner = owner
        self.name = name
        if self.view_name is None:
            self.view_name = self.view_name or f"{owner.__tablename__}_{name}"

        # Set up relationship
        if self.add_relationship:
            # Add the property that ensures initialization
            setattr(owner, f"{name}_relation", property(self._relationship_property))

        self.target_table = (
            self.target_table or f"{owner.__tablename__}_{self.name}_store"
        )
        self.set_schemas_correctly(owner)

        # Register vectorizer configuration

        metadata = owner.registry.metadata
        self._register_with_metadata(metadata)

    def _register_with_metadata(self, metadata: MetaData) -> None:
        """Register vectorizer configuration for migration generation"""
        if not hasattr(metadata, "info"):
            metadata.info = {}
        metadata.info.setdefault("pgai_managed_tables", set()).add(self.target_table)
        assert self.owner is not None

        vectorizers = metadata.info.setdefault("vectorizers", {})
        vectorizer_params = CreateVectorizerParams(
            source_table=self.owner.__tablename__,
            embedding=self.embedding_config,
            chunking=self.chunking_config,
            indexing=self.indexing_config,
            formatting_template=self.formatting_template,
            scheduling=self.scheduling_config,
            processing=self.processing_config,
            target_schema=self.target_schema,
            target_table=self.target_table,
            view_schema=self.view_schema,
            view_name=self.view_name,
            queue_schema=self.queue_schema,
            queue_table=self.queue_table,
            grant_to=self.grant_to,
            enqueue_existing=self.enqueue_existing,
        )

        vectorizers[f"{self.owner.__tablename__}.{self.name}"] = vectorizer_params
