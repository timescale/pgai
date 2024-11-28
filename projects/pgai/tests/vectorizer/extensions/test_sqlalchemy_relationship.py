import numpy as np
from click.testing import CliRunner
from sqlalchemy import Column, Engine, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session
from sqlalchemy.sql import text
from testcontainers.postgres import PostgresContainer  # type: ignore

from pgai.cli import vectorizer_worker
from pgai.configuration import (
    ChunkingConfig,
    OpenAIEmbeddingConfig,
)
from pgai.sqlalchemy import EmbeddingModel, VectorizerField


class Base(DeclarativeBase):
    pass


class BlogPost(Base):
    __tablename__ = "blog_posts"
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    content_embeddings = VectorizerField(
        embedding=OpenAIEmbeddingConfig(model="text-embedding-3-small", dimensions=768),
        chunking=ChunkingConfig(
            chunk_column="content", chunk_size=500, chunk_overlap=50
        ),
        formatting_template="Title: $title\nContent: $chunk",
        add_relationship=True,
    )

    content_embeddings_relation: Mapped[list[EmbeddingModel["BlogPost"]]]


def run_vectorizer_worker(db_url: str, vectorizer_id: int) -> None:
    CliRunner().invoke(
        vectorizer_worker,
        [
            "--db-url",
            db_url,
            "--once",
            "--vectorizer-id",
            str(vectorizer_id),
            "--concurrency",
            "1",
        ],
        catch_exceptions=False,
    )


def test_vectorizer_embedding_creation(
    postgres_container: PostgresContainer, initialized_engine: Engine
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
                    target_table => 'blog_posts_content_embeddings_store',
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
    run_vectorizer_worker(db_url, 1)

    # Verify embeddings were created
    with Session(initialized_engine) as session:
        # Verify embedding class was created correctly
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
        assert hasattr(blog_post, "content_embeddings_relation")
        assert blog_post.content_embeddings_relation is not None
        assert len(blog_post.content_embeddings_relation) > 0
        assert blog_post.content_embeddings_relation[0].chunk in blog_post.content

        embedding_entity = session.query(BlogPost.content_embeddings).first()
        assert embedding_entity is not None
        assert embedding_entity.chunk in blog_post.content
        assert embedding_entity.parent is not None