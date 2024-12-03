# SQLAlchemy Integration with pgAI Vectorizer

The `VectorizerField` is a SQLAlchemy helper type that integrates pgAI's vectorization capabilities directly into your SQLAlchemy models. This allows you to easily query vector embeddings created by pgai using familiar SQLAlchemy patterns.

## Installation

To use the SQLAlchemy integration, install pgAI with the SQLAlchemy extras:

```bash
pip install "pgai[sqlalchemy]"
```

## Basic Usage

Here's a basic example of how to use the `VectorizerField`:

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgai.sqlalchemy import VectorizerField, EmbeddingModel

class Base(DeclarativeBase):
    pass

class BlogPost(Base):
    __tablename__ = "blog_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    content: Mapped[str]

    # Add vector embeddings for the content field
    content_embeddings = VectorizerField(
        dimensions=768,
        add_relationship=True,
    )
    
    # Optional: Type hint for the relationship
    content_embeddings_relation: Mapped[list[EmbeddingModel["BlogPost"]]]
```

## Configuration

The `VectorizerField` accepts the following parameters:

- `dimensions` (int): The size of the embedding vector (required)
- `target_schema` (str, optional): Override the schema for the embeddings table. If not provided, inherits from the parent model's schema
- `target_table` (str, optional): Override the table name for embeddings. Default is `{table_name}_{field_name}_store`
- `add_relationship` (bool): Whether to automatically create a relationship to the embeddings table (default: False)

**Note:** The `VectorizerField` generates a new SQLAlchemy model, that is available under the attribute that you specify. If you are using alembics autogenerate functionality to generate migrations, you may need to exclude these models from the autogenerate process.
They are tagged with `pgai_managed=True`so you can simply exclude them by adding the following to your `env.py`:

```python
def include_object(object, name, type_, reflected, compare_to):
  if object.info.get("pgai_managed", False):
      return False
  return True

context.configure(
      connection=connection,
      target_metadata=target_metadata,
      include_object=include_object
  )
```

The model is only created at runtime, so depending on how your alembic migrations are set up this step could be skipped. Simply see what happens if you run `alembic revision --autogenerate` and if the model is included, add the above code.


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

We recommend adding this to a migration script and run it via alembic.

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

If `add_relationship=True`, you can access embeddings through the relationship field:

```python
blog_post = session.query(BlogPost).first()
for embedding in blog_post.content_embeddings_relation:  # Note: uses _relation suffix
    print(embedding.chunk)
```

### 3. Semantic Search

You can perform semantic similarity searches using [pgvector-pythons](https://github.com/pgvector/pgvector-python) distance functions:

```python
from sqlalchemy import func, text

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

You can combine embedding queries with regular SQL queries using the relationship:

```python
results = (
    session.query(BlogPost, BlogPost.content_embeddings)
    .join(BlogPost.content_embeddings_relation)
    .filter(BlogPost.title.ilike("%search term%"))
    .all()
)

for post, embedding in results:
    print(f"Title: {post.title}")
    print(f"Chunk: {embedding.chunk}")
```