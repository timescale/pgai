from typing import Any, Generic, TypeVar, cast, overload

from pgvector.sqlalchemy import Vector  # type: ignore
from sqlalchemy import ForeignKeyConstraint, Integer, Text, event, inspect
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Mapper,
    Relationship,
    RelationshipProperty,
    mapped_column,
    relationship,
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


def find_declarative_base(cls: type) -> type:
    """Find the SQLAlchemy declarative base class in the inheritance hierarchy."""
    for base in cls.__mro__:
        if (
            (
                hasattr(base, "_sa_registry")  # Modern style
                or hasattr(base, "__mapper__")  # Mapped class
                or hasattr(base, "metadata")  # Legacy style
            )
            and
            # Ensure it's the highest level base
            not any(hasattr(parent, "_sa_registry") for parent in base.__bases__)
        ):
            return base
    raise ValueError("No SQLAlchemy declarative base found in class hierarchy")


class _Vectorizer:
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
        self._relationship: RelationshipProperty[Any] | None = None
        self._initialized = False
        self.relationship_args = kwargs
        event.listen(Mapper, "after_configured", self._initialize_all)

    def _initialize_all(self):
        """Force initialization during mapper configuration"""
        if not self._initialized and self.owner is not None:
            self.__get__(None, self.owner)

    def set_schemas_correctly(self, owner: type[DeclarativeBase]) -> None:
        table_args = getattr(owner, "__table_args__", {})
        table_args_schema_name: str | None = None

        if isinstance(table_args, dict):
            table_args_schema_name = cast(str | None, table_args.get("schema"))  # type: ignore
        elif (
            isinstance(table_args, tuple)
            and len(table_args) > 0  # type: ignore
            and isinstance(table_args[-1], dict)
        ):
            table_args_schema_name = cast(str | None, table_args[-1].get("schema"))  # type: ignore

        self.target_schema = (
            self.target_schema
            or table_args_schema_name
            or owner.registry.metadata.schema
            or "public"
        )

    def create_embedding_class(
        self, owner: type[DeclarativeBase], parent_kwargs: dict[str, Any]
    ) -> type[EmbeddingModel[Any]]:
        assert self.name is not None
        table_name = self.target_table or f"{owner.__tablename__}_embedding_store"
        self.set_schemas_correctly(owner)
        class_name = f"{owner.__name__}{to_pascal_case(self.name)}"
        registry_instance = owner.registry
        base = find_declarative_base(owner)

        # Check if table already exists in metadata
        # There is probably a better way to do this
        # than accessing the internal _class_registry
        # Not doing this ends up in a recursion because
        # creating the new class reconfigures tha parent mapper
        # again triggering the after_configured event
        key = f"{self.target_schema}.{table_name}"
        if key in owner.metadata.tables:
            # Find the mapped class in the registry
            for cls in owner.registry._class_registry.values():  # type: ignore
                if hasattr(cls, "__table__") and cls.__table__.fullname == key:  # type: ignore
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
            "parent": relationship(
                owner,
                **parent_kwargs,
            ),
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

    @overload
    def __get__(
        self, obj: None, owner: type[DeclarativeBase]
    ) -> type[EmbeddingModel[Any]]: ...

    @overload
    def __get__(
        self, obj: DeclarativeBase, owner: type[DeclarativeBase]
    ) -> Relationship[EmbeddingModel[Any]]: ...

    def __get__(
        self, obj: DeclarativeBase | None, owner: type[DeclarativeBase]
    ) -> Relationship[EmbeddingModel[Any]] | type[EmbeddingModel[Any]]:
        assert self.name is not None
        relationship_name = f"_{self.name}_relationship"
        if not self._initialized:
            self._embedding_class = self.create_embedding_class(
                owner, self.relationship_args.pop("parent_kwargs", {})
            )

            mapper = inspect(owner)
            assert mapper is not None
            pk_cols = mapper.primary_key
            if not hasattr(owner, relationship_name):
                self.relationship_instance = relationship(
                    self._embedding_class,
                    foreign_keys=[
                        getattr(self._embedding_class, col.name) for col in pk_cols
                    ],
                    back_populates="parent",
                    **self.relationship_args,
                )
                setattr(owner, f"{self.name}_model", self._embedding_class)
                setattr(owner, relationship_name, self.relationship_instance)
            self._initialized = True
        if obj is None and self._initialized:
            return self._embedding_class  # type: ignore

        return getattr(obj, relationship_name)

    def __set_name__(self, owner: type[DeclarativeBase], name: str):
        self.owner = owner
        self.name = name

        metadata = owner.registry.metadata
        if not hasattr(metadata, "info"):
            metadata.info = {}
        metadata.info.setdefault("pgai_managed_tables", set()).add(self.target_table)


vectorizer_relationship = _Vectorizer
