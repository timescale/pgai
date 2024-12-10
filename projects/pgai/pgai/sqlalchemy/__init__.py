from typing import Any, Generic, TypeVar

from pgvector.sqlalchemy import Vector  # type: ignore
from sqlalchemy import ForeignKeyConstraint, Integer, Text, inspect, event
from sqlalchemy.orm import DeclarativeBase, Mapped, backref, mapped_column, relationship, add_mapped_attribute, Mapper
from sqlalchemy.orm.relationships import _RelationshipDeclared

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
        dimensions: int,
        target_schema: str | None = None,
        target_table: str | None = None,
        **kwargs: Any,
    ):
        self.dimensions = dimensions
        self.target_schema = target_schema
        self.target_table = target_table
        self.owner: type[DeclarativeBase] | None = None
        self.name: str | None = None
        self._embedding_class: type[EmbeddingModel[Any]] | None = None
        self._relationship: _RelationshipDeclared[Any] | None = None
        self._initialized = False
        self.relationship_args = kwargs
        event.listen(Mapper, 'after_configured', self._initialize_all)

    def _initialize_all(self):
        """Force initialization during mapper configuration"""
        if not self._initialized and self.owner is not None:
            self.__get__(None, self.owner)

    def _model_property(self, obj: Any = None) -> type[EmbeddingModel[Any]]:
        # Force initialization if not done yet
        if not self._initialized:
            _ = self.__get__(obj, self.owner)
        return self._embedding_class #type: ignore

    def set_schemas_correctly(self, owner: type[DeclarativeBase]) -> None:
        table_args_schema_name = getattr(owner, "__table_args__", {}).get("schema")
        self.target_schema = (
            self.target_schema
            or table_args_schema_name
            or owner.registry.metadata.schema
            or "public"
        )

    def create_embedding_class(
        self, owner: type[DeclarativeBase]
    ) -> type[EmbeddingModel[Any]]:
        assert self.name is not None
        table_name = self.target_table or f"{owner.__tablename__}_embedding_store"
        self.set_schemas_correctly(owner)
        class_name = f"{to_pascal_case(self.name)}Embedding"
        registry_instance = owner.registry
        base: type[DeclarativeBase] = owner.__base__  # type: ignore

        # Check if table already exists in metadata
        key = f"{self.target_schema}.{table_name}"
        if key in owner.metadata.tables:
            # Find the mapped class in the registry
            for cls in owner.registry._class_registry.values():
                if hasattr(cls, '__table__') and cls.__table__.fullname == key:
                    return cls  # type: ignore

        # Get primary key information from the fully initialized model
        mapper = inspect(owner)
        pk_cols = mapper.primary_key

        # Create the complete class dictionary
        class_dict: dict[str, Any] = {
            "__tablename__": table_name,
            "registry": registry_instance,
            # Add all standard columns
            "embedding_uuid": mapped_column(Text, primary_key=True),
            "chunk": mapped_column(Text, nullable=False),
            "embedding": mapped_column(Vector(self.dimensions), nullable=False),
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
    ) -> Mapped[list[EmbeddingModel[Any]]]:
        assert self.name is not None
        if not self._initialized:
            self._embedding_class = self.create_embedding_class(objtype)

            mapper = inspect(objtype)
            pk_cols = mapper.primary_key
            collection_name = f"{self.name}_collection"
            if not hasattr(objtype, collection_name):
                relationship_instance = relationship(
                    self._embedding_class,
                    collection_class=list,
                    foreign_keys=[
                        getattr(self._embedding_class, col.name) for col in pk_cols
                    ],
                    backref=self.relationship_args.pop("backref", backref("parent", lazy="joined")),
                    lazy="joined",
                )
                setattr(objtype, f"{self.name}_collection", relationship_instance)
            self._initialized = True
        if obj is None and self._initialized:
            return self._embedding_class

        return getattr(obj, f"{self.name}_collection")
        

    def __set_name__(self, owner: type[DeclarativeBase], name: str):
        self.owner = owner
        self.name = name
        # Set up the model property
        setattr(owner, f"{name}_model", property(self._model_property))

        metadata = owner.registry.metadata
        if not hasattr(metadata, "info"):
            metadata.info = {}
        metadata.info.setdefault("pgai_managed_tables", set()).add(self.target_table)


embedding_relation = Vectorizer