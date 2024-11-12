from typing import Optional, Protocol, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, select, Table, MetaData
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declared_attr
from sqlalchemy.sql.schema import SchemaItem


class SQLAlchemyModel(Protocol):
    __tablename__: str
    metadata: MetaData
    id: SchemaItem


class Vectorized:
    """Decorator that adds vector embedding functionality to SQLAlchemy models."""

    def __init__(
            self,
            model: str,
            dimensions: int,
            content_column: str,
            embedding_view: Optional[str] = None
    ):
        self.model = model
        self.dimensions = dimensions
        self.content_column = content_column
        self.embedding_view = embedding_view

    def __call__(self, cls):
        # Store the original table name
        source_table = cls.__tablename__

        # Default embedding view name if not provided
        view_name = self.embedding_view or f"{source_table}_embedding"

        @declared_attr
        def embeddings_view(cls: SQLAlchemyModel):
            # Create a Table object for the embeddings view
            return Table(
                view_name,
                cls.metadata,
                Column('id', cls.id.type),
                Column('embedding', Vector(self.dimensions)),
                Columm('chunk_seq', Column('chunk_seq', Integer)),
                Column('chunk', cls.__table__.c[self.content_column].type),
                extend_existing=True
            )

        # Add embedding property that maps to the view
        @hybrid_property
        def embedding(self):
            return getattr(self, '_embedding', None)

        @embedding.expression
        def embedding(cls):
            # Get the embeddings view table and reference its embedding column
            view = cls.embeddings_view
            return view.c.embedding

        # Add the properties to the class
        cls.embeddings_view = embeddings_view
        cls.embedding = embedding

        return cls