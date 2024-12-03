import numpy as np
from click.testing import CliRunner
from sqlalchemy import Column, Engine, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session
from sqlalchemy.sql import text
from testcontainers.postgres import PostgresContainer  # type: ignore

from pgai.cli import vectorizer_worker
from pgai.sqlalchemy import EmbeddingModel, VectorizerField


class Base(DeclarativeBase):
    pass


class Author(Base):
    __tablename__ = "authors"
    first_name = Column(Text, primary_key=True)
    last_name = Column(Text, primary_key=True)
    bio = Column(Text, nullable=False)
    bio_embeddings = VectorizerField(
        dimensions=768,
        add_relationship=True,
    )

    bio_embeddings_relation: Mapped[list[EmbeddingModel["Author"]]]


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


def test_vectorizer_composite_key(
    postgres_container: PostgresContainer, initialized_engine: Engine
):
    """Test vectorizer with a composite primary key."""
    db_url = postgres_container.get_connection_url()

    # Create tables
    metadata = Author.metadata
    metadata.create_all(initialized_engine, tables=[metadata.sorted_tables[0]])

    # Create vectorizer
    with initialized_engine.connect() as conn:
        conn.execute(
            text("""
                SELECT ai.create_vectorizer(
                    'authors'::regclass,
                    target_table => 'authors_bio_embeddings_store',
                    embedding => ai.embedding_openai('text-embedding-3-small', 768),
                    chunking =>
                    ai.chunking_recursive_character_text_splitter('bio', 50, 10)
                );
            """)
        )
        conn.commit()

    # Insert test data
    with Session(initialized_engine) as session:
        author = Author(
            first_name="Jane",
            last_name="Doe",
            bio="Jane is an accomplished researcher in artificial intelligence and machine learning. She has published numerous papers on neural networks.",  # noqa
        )
        session.add(author)
        session.commit()

    # Run vectorizer worker
    run_vectorizer_worker(db_url, 1)

    # Verify embeddings were created
    with Session(initialized_engine) as session:
        # Verify embedding class was created correctly
        assert Author.bio_embeddings.__name__ == "BioEmbeddingsEmbedding"

        # Check embeddings exist and have correct properties
        embedding = session.query(Author.bio_embeddings).first()
        assert embedding is not None
        assert isinstance(embedding.embedding, np.ndarray)
        assert len(embedding.embedding) == 768
        assert embedding.chunk is not None
        assert isinstance(embedding.chunk, str)

        # Check composite key fields were created
        assert hasattr(embedding, "first_name")
        assert hasattr(embedding, "last_name")
        assert embedding.first_name == "Jane"  # type: ignore
        assert embedding.last_name == "Doe"  # type: ignore

        # Verify relationship works
        author = session.query(Author).first()
        assert author is not None
        assert hasattr(author, "bio_embeddings_relation")
        assert author.bio_embeddings_relation is not None
        assert len(author.bio_embeddings_relation) > 0
        assert author.bio_embeddings_relation[0].chunk in author.bio

        # Test that parent relationship works
        embedding_entity = session.query(Author.bio_embeddings).first()
        assert embedding_entity is not None
        assert embedding_entity.chunk in author.bio
        assert embedding_entity.parent is not None
        assert embedding_entity.parent.first_name == "Jane"
        assert embedding_entity.parent.last_name == "Doe"

        # Test semantic search with composite keys
        from sqlalchemy import func

        # Search for content similar to "machine learning"
        similar_embeddings = (
            session.query(Author.bio_embeddings)
            .order_by(
                Author.bio_embeddings.embedding.cosine_distance(
                    func.ai.openai_embed(
                        "text-embedding-3-small",
                        "machine learning",
                        text("dimensions => 768"),
                    )
                )
            )
            .all()
        )

        assert len(similar_embeddings) > 0
        # The bio should contain machine learning related content
        assert "machine learning" in similar_embeddings[0].parent.bio
