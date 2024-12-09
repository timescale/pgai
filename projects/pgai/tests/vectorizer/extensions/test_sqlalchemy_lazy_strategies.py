from _pytest.logging import LogCaptureFixture
from click.testing import CliRunner
from sqlalchemy import Column, Integer, Text, Engine
from sqlalchemy.orm import DeclarativeBase, Session, Mapped
from sqlalchemy.sql import text
from testcontainers.postgres import PostgresContainer # type: ignore

from pgai.cli import vectorizer_worker
from pgai.sqlalchemy import Vectorizer, EmbeddingModel


class Base(DeclarativeBase):
    pass


class ArticleWithLazyStrategies(Base):
    __tablename__ = "articles_lazy_test"
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)

    # Different vectorizers with different lazy loading strategies
    select_embeddings = Vectorizer(
        dimensions=768,
        lazy="select",  # Default lazy loading (N+1 behavior)
        target_table="article_select_embedding_store"
    )

    joined_embeddings = Vectorizer(
        dimensions=768,
        lazy="joined",  # Load embeddings using JOIN
        target_table="article_joined_embedding_store"
    )
    
    select_embeddings_relation = Mapped[list[EmbeddingModel["ArticleWithLazyStrategies"]]]
    
    joined_embeddings_relation = Mapped[list[EmbeddingModel["ArticleWithLazyStrategies"]]]


def test_vectorizer_select_vs_joined_loading(
    postgres_container: PostgresContainer, initialized_engine: Engine, caplog: LogCaptureFixture
):
    """Test the difference between select and joined loading strategies."""
    db_url = postgres_container.get_connection_url()

    # Create tables

    metadata = ArticleWithLazyStrategies.metadata
    metadata.create_all(initialized_engine, tables=[metadata.sorted_tables[0]])

    # Create vectorizers in database
    with initialized_engine.connect() as conn:
        for table_suffix in ["select", "joined"]:
            conn.execute(
                text("""
                    SELECT ai.create_vectorizer(
                        'articles_lazy_test'::regclass,
                        target_table => 'article_' || :table_suffix || '_embedding_store',
                        view_name => 'article_' || :table_suffix || '_embeddings',
                        embedding => ai.embedding_openai('text-embedding-3-small', 768),
                        chunking => ai.chunking_recursive_character_text_splitter('content', 50, 10)
                    );
                    """).bindparams(table_suffix=table_suffix)
            )
        conn.commit()

    # Insert test data
    with Session(initialized_engine) as session:
        articles: list[ArticleWithLazyStrategies] = []
        for i in range(3):
            article = ArticleWithLazyStrategies(
                title=f"Test Article {i}",
                content=f"This is test content {i} that will be embedded."
            )
            session.add(article)
            articles.append(article)
        session.commit()

    # Run vectorizer worker for each vectorizer
    for i in range(1, 3):
        CliRunner().invoke(
            vectorizer_worker,
            [
                "--db-url",
                db_url,
                "--once",
                "--vectorizer-id",
                str(i),
                "--concurrency",
                "1",
            ],
            catch_exceptions=False,
        )

    with Session(initialized_engine) as session:
        session.expire_all()

        with caplog.at_level("DEBUG", "sqlalchemy.engine"):
            # Test select loading (should see N+1 behavior)
            articles = session.query(ArticleWithLazyStrategies).all()
            initial_queries = len([r for r in caplog.records if "SELECT" in r.message])
            # Access select embeddings - should trigger one query per article
            _ = [article.select_embeddings_relation for article in articles]
            after_select_queries = len([r for r in caplog.records if "SELECT" in r.message])
            # Should see N additional queries (one per article)
            assert after_select_queries == initial_queries + len(articles), \
                "Select loading should trigger one additional query per article"

            # Clear log
            caplog.clear()

            # Test joined loading
            session.expire_all()  # Ensure fresh loading state
            article = session.query(ArticleWithLazyStrategies).first()
            assert article is not None
            query_count = len([r for r in caplog.records if "SELECT" in r.message])
            # Access joined embeddings - should not trigger additional queries
            _ = article.joined_embeddings
            after_joined_count = len([r for r in caplog.records if "SELECT" in r.message])
            assert after_joined_count == query_count, \
                "Joined loading should not trigger additional queries"

            # Verify relationships loaded correctly
            for article in articles:
                assert hasattr(article, "select_embeddings")
                assert hasattr(article, "joined_embeddings")
                # Verify each has at least one embedding
                assert article.select_embeddings_relation is not None
                assert article.joined_embeddings_relation is not None
                assert len(article.select_embeddings_relation) > 0
                assert len(article.joined_embeddings_relation) > 0