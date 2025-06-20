from sqlalchemy import Column, Integer, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase

from pgai.sqlalchemy import vectorizer_relationship


class Base(DeclarativeBase):
    pass


class FeatureWithTupleTableArgs(Base):
    __tablename__ = "features_tuple"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    tenant_id = Column(Integer, nullable=False)

    __table_args__ = (UniqueConstraint("name", "tenant_id"),)

    embeddings = vectorizer_relationship(
        dimensions=1536, target_table="features_embeddings"
    )


def test_tuple_table_args():
    FeatureWithTupleTableArgs()
    embedding_class = FeatureWithTupleTableArgs.embeddings

    assert embedding_class is not None
