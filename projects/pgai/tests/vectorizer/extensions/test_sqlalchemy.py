from click.testing import CliRunner
from testcontainers.postgres import PostgresContainer #type: ignore

from pgai.cli import vectorizer_worker
from pgai.extensions.alembic.operations import (
    ChunkingConfig,
    EmbeddingConfig,
    FormattingConfig,
)
from pgai.extensions.sqlalchemy import VectorizerField


def test_sqlalchemy(postgres_container: PostgresContainer):
    from sqlalchemy import Column, Integer, Text, create_engine
    from sqlalchemy.orm import Session, declarative_base
    from sqlalchemy.sql import text
    db_url = postgres_container.get_connection_url()
    # Create engine and base
    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE EXTENSION IF NOT EXISTS ai CASCADE;
        """))
        conn.commit()
    Base = declarative_base()

    class BlogPost(Base):
        __tablename__ = "blog_posts"

        id = Column(Integer, primary_key=True)
        title = Column(Text, nullable=False)
        content = Column(Text, nullable=False)

        content_embeddings = VectorizerField(
            source_column="content",
            embedding=EmbeddingConfig(
                model="text-embedding-3-small",
                dimensions=768
            ),
            chunking=ChunkingConfig(
            chunk_column="chunk",
            chunk_size=500,
            chunk_overlap=50),
            formatting=FormattingConfig(
            template="Title: $title\nContent: $chunk"),
            add_relationship=True
        )

    # Create tables
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine, tables=[Base.metadata.sorted_tables[0]])

    # Create vectorizer
    with engine.connect() as conn:
        conn.execute(text("""
            SELECT ai.create_vectorizer( 
                'blog_posts'::regclass,
                embedding => ai.embedding_openai('text-embedding-3-small', 768),
                chunking => ai.chunking_recursive_character_text_splitter('content', 
                50,
                10)
            );
        """))
        conn.commit()

    # Insert test data
    with Session(engine) as session:
        posts = [
            BlogPost(
                title="Introduction to Machine Learning",
                content="Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience.",
            ),
            BlogPost(
                title="Python Programming",
                content="Python is a high-level programming language known for its simplicity and readability.",
            ),
            BlogPost(
                title="Data Science Basics",
                content="Data science combines statistics, programming, and domain expertise to extract insights from data.",
            ),
        ]
        session.add_all(posts)
        session.commit()

    CliRunner().invoke(
        vectorizer_worker,
        [
            "--db-url",
            db_url,
            "--once",
            "--vectorizer-id",
            "1",
            "--concurrency",
            "1",
        ],
        catch_exceptions=False,
    )

    # Wait a moment for the vectorizer to process
    import time
    time.sleep(5)  # You might need to adjust this based on your setup

    with Session(engine) as session:
        # Test 1: Access embedding class directly
        assert BlogPost.content_embeddings.__name__ == "BlogPostEmbedding"

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
                        text("dimensions => 768")
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
            .join(BlogPost.content_embeddings, BlogPost.id == BlogPost.content_embeddings.id)
            .filter(BlogPost.title.ilike("%Python%"))
            .all()
        )

        assert len(python_posts) > 0
        post, embedding = python_posts[0]
        assert "Python" in post.title
        assert hasattr(embedding, "embedding")

