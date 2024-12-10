from _pytest.logging import LogCaptureFixture
from click.testing import CliRunner
from sqlalchemy import Column, ForeignKey, Integer, Text, Engine, text
from pgvector.sqlalchemy import Vector  # type: ignore
from sqlalchemy.orm import DeclarativeBase, Session, relationship
from testcontainers.postgres import PostgresContainer

from pgai.cli import vectorizer_worker
from pgai.sqlalchemy import Vectorizer


class Base(DeclarativeBase):
    pass

# Regular SQLAlchemy version for comparison
class RegularEmbedding(Base):
    __tablename__ = "regular_embedding_store"

    embedding_uuid = Column(Text, primary_key=True)
    chunk = Column(Text, nullable=False)
    embedding = Column(Vector(768), nullable=False)
    chunk_seq = Column(Integer, nullable=False)
    article_id = Column(Integer, ForeignKey("articles_comparison.id", ondelete="CASCADE"))

    parent = relationship("ArticleComparison", back_populates="embeddings")

class ArticleComparison(Base):
    __tablename__ = "articles_comparison"

    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)

    # Regular SQLAlchemy relationship
    embeddings = relationship(
        "RegularEmbedding",
        lazy="joined",
        back_populates="parent"
    )

    # Your vectorizer relationship
    vectorizer_embeddings = Vectorizer(
        dimensions=768,
        lazy="joined",
        target_table="vectorizer_embedding_store"
    )

def test_relationship_comparison(
        postgres_container: PostgresContainer,
        initialized_engine: Engine,
        caplog: LogCaptureFixture
):
    """Compare behavior of regular SQLAlchemy relationship vs Vectorizer."""

    # Create tables
    metadata = ArticleComparison.metadata
    metadata.create_all(initialized_engine)

    # Set up vectorizer in database
    with initialized_engine.connect() as conn:
        conn.execute(
            text("""
                SELECT ai.create_vectorizer(
                    'articles_comparison'::regclass,
                    target_table => 'vectorizer_embedding_store',
                    view_name => 'vectorizer_embeddings',
                    embedding => ai.embedding_openai('text-embedding-3-small', 768),
                    chunking => ai.chunking_recursive_character_text_splitter('content', 50, 10)
                );
                """)
        )
        conn.commit()

    # Insert test data
    with Session(initialized_engine) as session:
        # Create article
        article = ArticleComparison(
            title="Test Article",
            content="This is test content that will be embedded."
        )
        session.add(article)
        session.commit()

        # Add regular embedding
        regular_embedding = RegularEmbedding(
            embedding_uuid="test-uuid",
            chunk="test chunk",
            embedding=[0.0] * 768,  # Dummy embedding
            chunk_seq=1,
            article_id=article.id
        )
        session.add(regular_embedding)
        session.commit()

    # Run vectorizer worker
    CliRunner().invoke(
        vectorizer_worker,
        [
            "--db-url",
            postgres_container.get_connection_url(),
            "--once",
            "--vectorizer-id",
            "1",
            "--concurrency",
            "1",
        ],
        catch_exceptions=False,
    )

    with Session(initialized_engine) as session:
        session.expire_all()

        with caplog.at_level("DEBUG", "sqlalchemy.engine"):

            # Compare relationship objects
            from sqlalchemy import inspect
            _ = ArticleComparison.vectorizer_embeddings
            regular_rel = inspect(ArticleComparison).relationships["embeddings"]
            vectorizer_rel = inspect(ArticleComparison).relationships["vectorizer_embeddings"]
            # Test regular relationship
            caplog.clear()
            article = session.query(ArticleComparison).first()
            regular_queries = [r.message for r in caplog.records if "SELECT" in r.message]
            print("\nRegular relationship queries:")
            print("\n".join(regular_queries))

            # Test vectorizer relationship
            caplog.clear()
            article = session.query(ArticleComparison).first()
            _ = article.vectorizer_embeddings  # Access the relationship
            vectorizer_queries = [r.message for r in caplog.records if "SELECT" in r.message]
            print("\nVectorizer relationship queries:")
            print("\n".join(vectorizer_queries))


            print("\nRegular relationship properties:")
            print(f"Lazy loading: {regular_rel.lazy}")
            print(f"Strategy: {regular_rel.strategy}")

            print("\nVectorizer relationship properties:")
            print(f"Lazy loading: {vectorizer_rel.lazy}")
            print(f"Strategy: {vectorizer_rel.strategy}")