# SQLAlchemy Integration with pgai Vectorizer

The `vectorizer_relationship` is a SQLAlchemy helper that integrates pgai's vectorization capabilities directly into your SQLAlchemy models.
Think of it as a normal SQLAlchemy [relationship](https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html), but with a preconfigured model instance under the hood.
This allows you to easily query vector embeddings created by pgai using familiar SQLAlchemy patterns.

## Installation

To use the SQLAlchemy integration, install pgai with the SQLAlchemy extras:

```bash
pip install "pgai[sqlalchemy]"
```

## Basic Usage

Here's a basic example of how to use the `vectorizer_relationship`:

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgai.sqlalchemy import vectorizer_relationship

class Base(DeclarativeBase):
    pass

class BlogPost(Base):
    __tablename__ = "blog_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    content: Mapped[str]

    # Add vector embeddings for the content field
    content_embeddings = vectorizer_relationship(
        dimensions=768
    )
```
Note if you work with alembics autogenerate functionality for migrations, also check [Working with alembic](#working-with-alembic).

### Semantic Search

You can then perform semantic similarity search on the field using [pgvector-python's](https://github.com/pgvector/pgvector-python) distance functions:

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
```

Or if you already have the embeddings in your application:

```python
similar_posts = (
    session.query(BlogPost.content_embeddings)
    .order_by(
        BlogPost.content_embeddings.embedding.cosine_distance(
            [3, 1, 2]
        )
    )
    .limit(5)
    .all()
)
```

## Configuration

The `vectorizer_relationship` accepts the following parameters:

- `dimensions` (int): The size of the embedding vector (required)
- `target_schema` (str, optional): Override the schema for the embeddings table. If not provided, inherits from the parent model's schema
- `target_table` (str, optional): Override the table name for embeddings. Default is `{table_name}_embedding_store`

Additional parameters are simply forwarded to the underlying [SQLAlchemy relationship](https://docs.sqlalchemy.org/en/20/orm/relationships.html) so you can configure it as you desire.

Think of the `vectorizer_relationship` as a normal SQLAlchemy relationship, but with a preconfigured model instance under the hood.


## Setting up the Vectorizer

After defining your model, you need to create the vectorizer using pgai's SQL functions:

```sql
SELECT ai.create_vectorizer(
    'blog_posts'::regclass,
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

The `vectorizer_relationship` provides several ways to work with embeddings:

### 1. Direct Access to Embeddings

If you access the class proeprty of your model the `vectorizer_relationship` provide a SQLAlchemy model that you can query directly:

```python
# Get all embeddings
embeddings = session.query(BlogPost.content_embeddings).all()

# Access embedding properties
for embedding in embeddings:
    print(embedding.embedding)  # The vector embedding
    print(embedding.chunk)      # The text chunk
```
The model will have the primary key fields of the parent model as well as the following fields:
- `chunk` (str): The text chunk that was embedded
- `embedding` (Vector): The vector embedding
- `chunk_seq` (int): The sequence number of the chunk
- `embedding_uuid` (str): The UUID of the embedding
- `parent` (ParentModel): The parent model instance

### 2. Relationship Access


```python
blog_post = session.query(BlogPost).first()
for embedding in blog_post.content_embeddings:
    print(embedding.chunk)
```
Access the original posts through the parent relationship
```python
for embedding in similar_posts:
    print(embedding.parent.title)
```

### 3. Join Queries

You can combine embedding queries with regular SQL queries using the relationship:

```python
results = (
    session.query(BlogPost, BlogPost.content_embeddings)
    .join(BlogPost.content_embeddings)
    .filter(BlogPost.title.ilike("%search term%"))
    .all()
)

for post, embedding in results:
    print(f"Title: {post.title}")
    print(f"Chunk: {embedding.chunk}")
```

## Working with alembic 


The `vectorizer_relationship` generates a new SQLAlchemy model, that is available under the attribute that you specify. If you are using alembic's autogenerate functionality to generate migrations, you will need to exclude these models from the autogenerate process.
These are added to a list in your metadata called `pgai_managed_tables` and you can exclude them by adding the following to your `env.py`:

```python
def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in target_metadata.info.get("pgai_managed_tables", set()):
        return False
    return True

context.configure(
      connection=connection,
      target_metadata=target_metadata,
      include_object=include_object
  )
```

This should now prevent alembic from generating tables for these models when you run `alembic revision --autogenerate`.
