from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.orm import declared_attr, relationship
from sqlalchemy.ext.hybrid import hybrid_property


def Vectorized(
        model: str,
        dimensions: int,
        content_column: str,
):
    def wrapper(cls):
        # Original table name is needed for creating the embeddings table
        source_table = cls.__tablename__
        base = cls.__base__

        # Create embeddings table dynamically
        class VectorizedMixin:
            @declared_attr
            def __tablename__(cls) -> str:
                return f"{source_table}_embeddings"

            @declared_attr
            def source_id(cls):
                return Column(Integer, ForeignKey(f"{source_table}.id"), nullable=False)

            @declared_attr
            def chunk_seq(cls):
                return Column(Integer, nullable=False)

            @declared_attr
            def chunk(cls):
                return Column(Text, nullable=False)

            @declared_attr
            def embedding(cls):
                return Column(Vector(768), nullable=False)

        # Create the embeddings model
        class Embeddings(VectorizedMixin, base):
            __table_args__ = {"extend_existing": True}
            id = Column(Integer, primary_key=True)

        # Add relationship to original model
        cls._embeddings = relationship(
            Embeddings,
            primaryjoin=f"{cls.__name__}.id==Embeddings.source_id",
            order_by=Embeddings.chunk_seq,
            lazy="select"
        )

        # Add hybrid property for the embedding
        @hybrid_property
        def embedding(self):
            """Returns a queryable interface to the embeddings"""
            # In Python, returns the first embedding (we can improve this later)
            if self._embeddings:
                return self._embeddings[0].embedding
            return None

        @embedding.expression
        def embedding(cls):
            """Allows querying against embeddings in SQL"""
            # In SQL, joins with embeddings table and uses first embedding
            return Embeddings.embedding.label("embedding")

        cls.embedding = embedding
        cls.Embeddings = Embeddings

        # Store metadata for vectorizer creation during migrations
        cls.__pgai_vectorizer__ = {
            "model": model,
            "dimensions": dimensions,
            "content_column": content_column,
        }

        return cls

    return wrapper