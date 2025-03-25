from typing import Any

import numpy as np
from sqlalchemy import Column, Engine, Integer, Text, select
from sqlalchemy.orm import DeclarativeBase, Session, joinedload
from sqlalchemy.sql import text
from testcontainers.postgres import PostgresContainer  # type: ignore

from pgai.sqlalchemy import vectorizer_relationship
from tests.vectorizer.cli.conftest import run_vectorizer_worker


class Base(DeclarativeBase):
    pass


class BlogPost(Base):
    __tablename__ = "blog_posts"
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    content_embeddings = vectorizer_relationship(dimensions=768, lazy="joined")


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
        run_vectorizer_worker(db_url, 1)

    # Verify embeddings were created
    with Session(initialized_engine) as session:
        # Verify embedding class was created correctly

        blog_post = session.query(BlogPost).first()
        assert blog_post is not None
        assert blog_post.content_embeddings is not None
        assert BlogPost.content_embeddings.__name__ == "BlogPostContentEmbeddings"

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


def test_select_parent(
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
        run_vectorizer_worker(db_url, 1)

    # Verify embeddings were created
    with Session(initialized_engine) as session:
        # Check embeddings exist and have correct properties
        embedding = (
            session.execute(
                select(BlogPost.content_embeddings).options(
                    joinedload(BlogPost.content_embeddings.parent)  # type: ignore
                )
            )
            .scalars()
            .first()
        )
        assert embedding is not None
        assert embedding.parent is not None


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    content = Column(Text())
    content_embeddings = vectorizer_relationship(dimensions=768, lazy="joined")


def test_can_build_select():
    """
    This is a very minimal test case that failed when doing
    some development with the extension.
    The nature of the vectorizer_relationship being a descriptor messes
    with sqlalchemys relationship resolution.
    It was previously using `backref` to propagate the parent field,
    which is resolved later and an immediate access
    to build queries like this would fail.
    """
    select(Document.content_embeddings).options(
        joinedload(Document.content_embeddings.parent)  # type: ignore
    )
