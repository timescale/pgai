from typing import Any

from sqlalchemy import Column, Engine, Integer, Text
from sqlalchemy.orm import Session, declarative_base
from sqlalchemy.sql import text
from testcontainers.postgres import PostgresContainer  # type: ignore

from pgai.sqlalchemy import vectorizer_relationship
from tests.vectorizer.extensions.utils import run_vectorizer_worker


def test_sqlalchemy(
    postgres_container: PostgresContainer, initialized_engine: Engine, vcr_: Any
):
    db_url = postgres_container.get_connection_url()
    # Create engine and base
    Base = declarative_base()

    class BlogPost(Base):
        __tablename__ = "blog_posts"

        id = Column(Integer, primary_key=True)
        title = Column(Text, nullable=False)
        content = Column(Text, nullable=False)

        content_embeddings = vectorizer_relationship(
            dimensions=768,
        )

    # Create tables
    Base.metadata.drop_all(initialized_engine)
    Base.metadata.create_all(
        initialized_engine, tables=[Base.metadata.sorted_tables[0]]
    )

    # Create vectorizer
    with initialized_engine.connect() as conn:
        conn.execute(
            text("""
            SELECT ai.create_vectorizer(
                'blog_posts'::regclass,
                embedding => ai.embedding_openai('text-embedding-3-small', 768),
                chunking => ai.chunking_recursive_character_text_splitter('content',
                50,
                10)
            );
        """)
        )
        conn.commit()

    # Insert test data
    with Session(initialized_engine) as session:
        posts = [
            BlogPost(
                title="Introduction to Machine Learning",
                content="Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience.",  # noqa
            ),
            BlogPost(
                title="Python Programming",
                content="Python is a high-level programming language known for its simplicity and readability.",  # noqa
            ),
            BlogPost(
                title="Data Science Basics",
                content="Data science combines statistics, programming, and domain expertise to extract insights from data.",  # noqa
            ),
        ]
        session.add_all(posts)
        session.commit()

    with vcr_.use_cassette("test_sqlalchemy.yaml"):
        run_vectorizer_worker(db_url, 1)

    with Session(initialized_engine) as session:
        # Test 1: Access embedding class directly
        assert BlogPost.content_embeddings.__name__ == "ContentEmbeddingsEmbedding"

        # Get all embeddings directly
        all_embeddings = session.query(BlogPost.content_embeddings).all()
        assert len(all_embeddings) > 0
        assert hasattr(all_embeddings[0], "embedding")
        assert hasattr(all_embeddings[0], "chunk")

        # Test 2: Access embeddings through relationship
        blog_post = session.query(BlogPost).first()
        assert blog_post is not None

        embedding = session.query(BlogPost.content_embeddings).first()
        assert embedding is not None
        assert embedding.chunk in blog_post.content

        # Test 4: Semantic search functionality
        from sqlalchemy import func

        # Search for content similar to "artificial intelligence"
        similar_embeddings = (
            session.query(BlogPost.content_embeddings)
            .order_by(
                BlogPost.content_embeddings.embedding.cosine_distance(
                    func.ai.openai_embed(
                        "text-embedding-3-small",
                        "artificial intelligence",
                        text("dimensions => 768"),
                    )
                )
            )
            .limit(2)
            .all()
        )

        assert len(similar_embeddings) > 0
        # The ML post should be most similar to "artificial intelligence"
        assert "Machine learning" in similar_embeddings[0].parent.content

        # Test 5: Join query example
        # Find all blog posts with their embeddings where title contains "Python"
        python_posts = (
            session.query(BlogPost, BlogPost.content_embeddings)
            .join(
                BlogPost.content_embeddings,
                BlogPost.id == BlogPost.content_embeddings.id,  # type: ignore
            )
            .filter(BlogPost.title.ilike("%Python%"))
            .all()
        )

        assert len(python_posts) > 0
        post, embedding = python_posts[0]
        assert "Python" in post.title
        assert hasattr(embedding, "embedding")
