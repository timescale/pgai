from click.testing import CliRunner
from sqlalchemy import select
from testcontainers.postgres import PostgresContainer

from pgai.cli import vectorizer_worker
from pgai.extensions.sqlalchemy import Vectorized

def test_sqlalchemy(postgres_container: PostgresContainer):
    from sqlalchemy import create_engine, Column, Integer, Text, func
    from sqlalchemy.orm import declarative_base, Session
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

    @Vectorized(
        model="text-embedding-3-small",
        dimensions=768,
        content_column="content",
    )
    class BlogPost(Base):
        __tablename__ = "blog_posts"

        id = Column(Integer, primary_key=True)
        title = Column(Text, nullable=False)
        content = Column(Text, nullable=False)

    # Create tables
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    # Create vectorizer
    with engine.connect() as conn:
        conn.execute(text("""
            SELECT ai.create_vectorizer( 
                'blog_posts'::regclass,
                embedding => ai.embedding_openai('text-embedding-3-small', 768),
                chunking => ai.chunking_recursive_character_text_splitter('content')
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

    # Find similar posts
    def find_with_vector(session):
        return (
            session.query(
                BlogPost.id,
                BlogPost.title,
                BlogPost.content,
                #BlogPost.chunk_seq,
                #BlogPost.chunk,
                BlogPost.embedding,
            )
        )
    
    def get_all_blog_posts(session):
        return(
            session.query(BlogPost).all()
        )

    # Test the semantic search
    with Session(engine) as session:
        # Search for posts similar to a query about AI
        posts = get_all_blog_posts(session)
        post_list = list(posts)
        print(f"Found {len(post_list)} Posts with ids: {','.join([str(post.id) for post in post_list])}")
        print(f"Type of post: {type(post_list[0])}")

        for post in posts:
            print(f"\nTitle: {post.title}")
            print(f"Content: {post.content}")
            print(f"Embedding: {post.embedding}")


