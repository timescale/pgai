# SQLAlchemy Integration with pgAI Vectorizer

The `VectorizerField` is a custom SQLAlchemy field type that integrates pgAI's vectorization capabilities directly into your SQLAlchemy models. This allows you to easily create, manage, and query vector embeddings for your text data using familiar SQLAlchemy patterns.

## Installation

To use the SQLAlchemy integration, install pgAI with the SQLAlchemy extras:

```bash
pip install "pgai[sqlalchemy]"
```

## Basic Usage

Here's a basic example of how to use the `VectorizerField`:

```python
from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import declarative_base
from pgai.sqlalchemy import VectorizerField

Base = declarative_base()

class BlogPost(Base):
    __tablename__ = "blog_posts"

    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)

    # Add vector embeddings for the content field
    content_embeddings = VectorizerField(
        dimensions=768,
        add_relationship=True,
    )
```

## Configuration

The `VectorizerField` accepts the following parameters:

- `dimensions` (int): The size of the embedding vector (required)
- `add_relationship` (bool): Whether to automatically create a relationship to the embeddings table (default: True)

## Setting up the Vectorizer

After defining your model, you need to create the vectorizer using pgAI's SQL functions:

```sql
SELECT ai.create_vectorizer(
    'blog_posts'::regclass,
    target_table => 'blog_posts_content_embeddings_store',
    embedding => ai.embedding_openai('text-embedding-3-small', 768),
    chunking => ai.chunking_recursive_character_text_splitter(
        'content',
        50,  -- chunk_size
        10   -- chunk_overlap
    )
);
```

## Querying Embeddings

The `VectorizerField` provides several ways to work with embeddings:

### 1. Direct Access to Embeddings

```python
# Get all embeddings
embeddings = session.query(BlogPost.content_embeddings).all()

# Access embedding properties
for embedding in embeddings:
    print(embedding.embedding)  # The vector embedding
    print(embedding.chunk)      # The text chunk
```

### 2. Relationship Access

If `add_relationship=True`, you can access embeddings through the model relationship:

```python
blog_post = session.query(BlogPost).first()
for embedding in blog_post.content_embeddings:
    print(embedding.chunk)
```

### 3. Semantic Search

You can perform semantic similarity searches using cosine distance:

```python
from sqlalchemy import func

similar_posts = (
    session.query(BlogPost.content_embeddings)
    .order_by(
        BlogPost.content_embeddings.embedding.cosine_distance(
            func.ai.openai_embed(
                "text-embedding-3-small",
                "search query",
                text("dimensions => 768")
            )
        )
    )
    .limit(5)
    .all()
)

# Access the original posts through the parent relationship
for embedding in similar_posts:
    print(embedding.parent.title)
```

### 4. Join Queries

You can combine embedding queries with regular SQL queries:

```python
results = (
    session.query(BlogPost, BlogPost.content_embeddings)
    .join(
        BlogPost.content_embeddings,
        BlogPost.id == BlogPost.content_embeddings.id,
    )
    .filter(BlogPost.title.ilike("%search term%"))
    .all()
)

for post, embedding in results:
    print(f"Title: {post.title}")
    print(f"Chunk: {embedding.chunk}")
```

## Generated Tables and Relationships

When you use a `VectorizerField`, it creates:

1. A table for storing embeddings (default name: `{table_name}_{field_name}_store`)
2. A one-to-many relationship between your model and the embeddings
3. A relationship from embeddings back to the parent model