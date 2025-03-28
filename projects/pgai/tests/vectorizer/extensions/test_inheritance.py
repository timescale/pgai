from datetime import datetime
from typing import Any

import numpy as np
from sqlalchemy import Column, Engine, Integer, func, text
from sqlalchemy import Text as sa_Text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from testcontainers.postgres import PostgresContainer  # type: ignore

from pgai.sqlalchemy import vectorizer_relationship
from tests.vectorizer.cli.conftest import run_vectorizer_worker


class BaseModel(DeclarativeBase):
    pass


class TimeStampedBase(BaseModel):
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
    __abstract__ = True


class BlogPost(TimeStampedBase):
    __tablename__ = "blog_posts"
    id = Column(Integer, primary_key=True)
    title = Column(sa_Text, nullable=False)
    content = Column(sa_Text, nullable=False)
    content_embeddings = vectorizer_relationship(dimensions=768, lazy="joined")


def test_vectorizer_embedding_creation(
    postgres_container: PostgresContainer, initialized_engine: Engine, vcr_: Any
):
    """Test basic embedding creation and querying while the Model inherits from
    another abstract model. This previously caused issues where the embedding model
    inherited the fields as well which should not be the case."""
    db_url = postgres_container.get_connection_url()
    metadata = BlogPost.metadata
    metadata.create_all(initialized_engine, tables=[metadata.sorted_tables[0]])
    with initialized_engine.connect() as conn:
        conn.execute(
            text("""
                SELECT ai.create_vectorizer(
                    'blog_posts'::regclass,
                    loading => ai.loading_column(column_name => 'content'),
                    embedding =>
                    ai.embedding_openai('text-embedding-3-small', 768),
                    chunking =>
                    ai.chunking_recursive_character_text_splitter(50, 10)
                );
            """)
        )
        conn.commit()

    # Insert test data
    with Session(initialized_engine) as session:
        post = BlogPost(
            title="Introduction to Machine Learning",
            content="Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience.",  # noqa
        )
        session.add(post)
        session.commit()

    # Run vectorizer worker
    with vcr_.use_cassette("test_vectorizer_embedding_creation_relationship.yaml"):
        result = run_vectorizer_worker(db_url, 1)
        assert result.exit_code == 0

    with Session(initialized_engine) as session:
        blog_post = session.query(BlogPost).first()
        assert blog_post is not None
        assert blog_post.content_embeddings is not None
        assert BlogPost.content_embeddings.__name__ == "BlogPostContentEmbeddings"

        # Check embeddings exist and have correct properties
        embedding = session.query(BlogPost.content_embeddings).first()
        assert embedding is not None
        assert isinstance(embedding.embedding, np.ndarray)
        assert len(embedding.embedding) == 768
        assert embedding.chunk is not None
        assert isinstance(embedding.chunk, str)
