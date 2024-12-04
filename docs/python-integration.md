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
from pgai.configuration import OpenAIEmbeddingConfig, ChunkingConfig

class Base(DeclarativeBase):
    pass

class BlogPost(Base):
    __tablename__ = "blog_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    content: Mapped[str]

    # Add vector embeddings for the content field
    content_embeddings = VectorizerField(
        embedding=OpenAIEmbeddingConfig(
            model="text-embedding-3-small",
            dimensions=768
        ),
        chunking=ChunkingConfig.recursive_character_text_splitter(
            source_column="content",
            chunk_size=50,
            chunk_overlap=10
        ),
        add_relationship=True,
    )
    
    # Optional: Type hint for the relationship
    content_embeddings_relation: Mapped[list[EmbeddingModel["BlogPost"]]]
```

## Configuration

The `VectorizerField` accepts the same parameters as the [SQL API](vectorizer-api-reference.md). One difference to the SQL API is, that it uses the name of the variable to determine the target table name. In the example above, the target table will be named `blog_posts_content_embeddings_store`. This allows you to add as many vectorizers to your table as you like, without worrying about the table naming.

**Note:** The `VectorizerField` generates a new SQLAlchemy model, that is available under the attribute that you specify. If you are using alembics autogenerate functionality to generate migrations, you may need to exclude these models from the autogenerate process:

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

## Setting up the Vectorizer via migrations

pgai provides native Alembic operations for managing vectorizers. For them to work you need to run `setup_alembic` in your env.py file. Which registers the pgai operations under the global op context:

```python
from pgai.alembic import register_operations

register_operations()
```

Then you can use the `create_vectorizer` operation to create a vectorizer for your model. As well as the `drop_vectorizer` operation to remove it.

```python
from alembic import op
from pgai.configuration import (
    OpenAIEmbeddingConfig,
    ChunkingConfig,
    DiskANNIndexingConfig
)


def upgrade() -> None:
    op.create_vectorizer(
        source_table="blog_posts",
        target_table="blog_posts_content_embeddings_store",
        embedding=OpenAIEmbeddingConfig(
            model="text-embedding-3-small",
            dimensions=768
        ),
        chunking=ChunkingConfig.recursive_character_text_splitter(
            source_column="content",
            chunk_size=50,
            chunk_overlap=10
        ),
        indexing=DiskANNIndexingConfig(
            min_rows=10,
            num_dimensions=768
        )
    )


def downgrade() -> None:
    op.drop_vectorizer(vectorizer_id=1, drop_all=True)
```

The `create_vectorizer` operation supports all configuration options available in the [SQL API](vectorizer-api-reference.md).

## Alembic autogenerate

Instead of manually repeating all the configuration from the `VectorizerField` in the `create_vectorizer` operation, you can also make use of alembics autogenerate functionality.
Simply import `enable_vectorizer_autogenerate` and run it in your env.py file:
```python
from pgai.alembic import register_operations, enable_vectorizer_autogenerate

register_operations()
enable_vectorizer_autogenerate()
```    

Now when you run `alembic revision --autogenerate ...` alembic will automatically detect the `VectorizerField` and generate the corresponding `create_vectorizer` operations in your migration files.

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