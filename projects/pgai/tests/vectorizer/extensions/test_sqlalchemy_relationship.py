from typing import Any

import numpy as np
from sqlalchemy import Column, Engine, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.sql import text
from testcontainers.postgres import PostgresContainer  # type: ignore

from pgai.sqlalchemy import vectorizer_relationship
from tests.vectorizer.extensions.utils import run_vectorizer_worker


class Base(DeclarativeBase):
    pass


class BlogPost(Base):
    __tablename__ = "blog_posts"
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    content_embeddings = vectorizer_relationship(
        dimensions=768,
    )


def test_vectorizer_embedding_creation(
    postgres_container: PostgresContainer, initialized_engine: Engine, vcr_: Any
):
    """Test basic data insertion and embedding generation with default relationship."""
    db_url = postgres_container.get_connection_url()
    # Create tables
    metadata = BlogPost.metadata
    metadata.create_all(initialized_engine, tables=[metadata.sorted_tables[0]])
    with initialized_engine.connect() as conn:
        conn.execute(
            text("""
                SELECT ai.create_vectorizer(
                    'blog_posts'::regclass,
                    embedding =>
                    ai.embedding_openai('text-embedding-3-small', 768),
                    chunking =>
                    ai.chunking_recursive_character_text_splitter('content', 50, 10)
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
        run_vectorizer_worker(db_url, 1)

    # Verify embeddings were created
    with Session(initialized_engine) as session:
        # Verify embedding class was created correctly

        blog_post = session.query(BlogPost).first()
        assert blog_post is not None
        assert blog_post.content_embeddings is not None
        assert BlogPost.content_embeddings.__name__ == "ContentEmbeddingsEmbedding"

        # Check embeddings exist and have correct properties
        embedding = session.query(BlogPost.content_embeddings).first()
        assert embedding is not None
        assert isinstance(embedding.embedding, np.ndarray)
        assert len(embedding.embedding) == 768
        assert embedding.chunk is not None  # Should have chunk text
        assert isinstance(embedding.chunk, str)

        # Verify relationship works
        blog_post = session.query(BlogPost).first()
        assert blog_post is not None
        assert hasattr(blog_post, "content_embeddings")
        assert blog_post.content_embeddings is not None
        assert len(blog_post.content_embeddings) > 0  # type: ignore
        assert blog_post.content_embeddings[0].chunk in blog_post.content

        embedding_entity = session.query(BlogPost.content_embeddings).first()
        assert embedding_entity is not None
        assert embedding_entity.chunk in blog_post.content
        assert embedding_entity.parent is not None
