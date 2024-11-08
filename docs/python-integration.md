# Python Integration

Once you've installed pgai on your database, you'll likely want to integrate it into your Python application. The `pgai` Python package provides seamless integration with SQLAlchemy and Alembic to make working with vectors and LLM queries as natural as working with any other database feature.

## Installation

```bash
pip install pgai
```

## Key Features

- Declarative vectorizer configuration using model annotations
- Type-safe AI function calls in queries
- Automatic migration generation for vectorizers
- Native vector type support
- Simplified semantic search queries

## Basic Usage

### Defining Models with Vectorizers

Use the `@vectorized` decorator to automatically configure vectorizers for your models:

```python
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from pgai.sqlalchemy import vectorized, Embedding

class Base(DeclarativeBase):
    pass

@vectorized(
    embedding_model="text-embedding-3-small",
    chunk_column="content",
    chunk_size=1000
)
class BlogPost(Base):
    __tablename__ = "blog_posts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    
    # The embedding will be automatically managed by pgai
    embedding: Mapped[Embedding] = mapped_column(Embedding(1536))
```

The `@vectorized` decorator automatically:
- Configures the pgai vectorizer for your model
- Generates the necessary database objects
- Creates migration operations (when using Alembic)
- Sets up the embedding view

### Querying with Semantic Search

The package provides SQLAlchemy extensions for working with AI functions and vector operations:

```python
from pgai.sqlalchemy import semantic_search, openai_embed
from sqlalchemy import select

# Simple semantic search query
results = session.execute(
    select(BlogPost)
    .order_by(
        semantic_search(
            BlogPost.embedding,
            "How to optimize PostgreSQL?"
        )
    )
    .limit(5)
).scalars()

# Or use the AI functions directly in queries
results = session.execute(
    select(BlogPost)
    .where(
        BlogPost.embedding.cosine_distance(
            openai_embed("text-embedding-3-small", "database optimization")
        ) < 0.3
    )
).scalars()
```

## Working with Migrations

### Alembic Integration

The pgai Alembic integration automatically generates the necessary migration operations for your vectorized models:

```python
# migrations/versions/123456789_add_blog_posts.py
from alembic import op
import sqlalchemy as sa
from pgai.alembic import create_vectorizer, drop_vectorizer

def upgrade():
    # Regular table creation
    op.create_table(
        'blog_posts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Automatically generated vectorizer operations
    create_vectorizer(
        'blog_posts',
        embedding_model='text-embedding-3-small',
        chunk_column='content'
    )

def downgrade():
    drop_vectorizer('blog_posts')
    op.drop_table('blog_posts')
```

## Advanced Features

### Custom Embedding Formats

You can customize how text is prepared for embedding:

```python
@vectorized(
    embedding_model="text-embedding-3-small",
    chunk_column="content",
    format_template="Title: ${title}\nContent: ${chunk}"
)
class BlogPost(Base):
    # ... model definition as before
```

...
