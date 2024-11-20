# SQLAlchemy Integration

pgai provides SQLAlchemy integration for managing and querying vector embeddings in your database through a simple declarative interface.

## VectorizerField

### Basic Setup

```python
from sqlalchemy import Column, Integer, Text
from sqlalchemy.orm import DeclarativeBase
from pgai.extensions.sqlalchemy import VectorizerField
from pgai.extensions import EmbeddingConfig

class BlogPost(DeclarativeBase):
    __tablename__ = "blog_posts"
    
    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    
    content_embeddings = VectorizerField(
        source_column="content",
        embedding=EmbeddingConfig(
            model="text-embedding-3-small",
            dimensions=768
        )
    )
```

### Querying with VectorizerField

Once your model is set up, you can query the embeddings in several ways:

#### Basic ORM Queries

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

# Get all embeddings
with Session(engine) as session:
    # Get embedding entries
    embeddings = session.query(BlogPost.content_embeddings).all()
    
    # Access embedding vectors and chunks
    for embedding in embeddings:
        vector = embedding.embedding  # numpy array of embeddings
        chunk = embedding.chunk      # text chunk that was embedded
        chunk_seq = embedding.chunk_seq  # sequence number of chunk
```

#### Semantic Search

Using pgvector's distance operators in queries:

```python
from sqlalchemy import func

def search_similar_content(session: Session, query_text: str, limit: int = 5):
    # Generate embedding for search query
    return (
        session.query(
            BlogPost.content_embeddings,
            BlogPost.title,
            # Calculate and include distance in results
            BlogPost.content_embeddings.embedding.cosine_distance(
                func.ai.openai_embed(
                    'text-embedding-3-small',
                    query_text,
                    text('dimensions => 768')
                )
            ).label('distance')
        )
        .order_by('distance')  # Sort by similarity
        .limit(limit)
        .all()
    )

# Usage:
results = search_similar_content(session, "machine learning concepts")
for embedding, title, distance in results:
    print(f"Title: {title}")
    print(f"Matching chunk: {embedding.chunk}")
    print(f"Distance: {distance}\n")
```

#### Advanced Filtering

```python
# Find content within a certain distance threshold
threshold_query = (
    session.query(BlogPost.content_embeddings)
    .filter(
        BlogPost.content_embeddings.embedding.cosine_distance(
            func.ai.openai_embed(
                'text-embedding-3-small',
                'search query',
                text('dimensions => 768')
            )
        ) < 0.3
    )
)

# Combine with regular SQL filters
combined_query = (
    session.query(BlogPost, BlogPost.content_embeddings)
    .join(
        BlogPost.content_embeddings,
        BlogPost.id == BlogPost.content_embeddings.id,
    )
    .filter(BlogPost.title.ilike("%Python%"))
    .order_by(
        BlogPost.content_embeddings.embedding.cosine_distance(
            func.ai.openai_embed(
                'text-embedding-3-small',
                'search query',
                text('dimensions => 768')
            )
        )
    )
)
```

### Model Relationships

You can optionally create SQLAlchemy relationships between your model and its embeddings:

```python
from sqlalchemy.orm import Mapped
from pgai.extensions.sqlalchemy import EmbeddingModel

class BlogPost(DeclarativeBase):
    # ... other columns as above ...
    
    content_embeddings = VectorizerField(
        source_column="content",
        embedding=EmbeddingConfig(
            model="text-embedding-3-small", 
            dimensions=768
        ),
        add_relationship=True
    )
    
    # Type hint for the relationship
    content_embeddings_relation: Mapped[list[EmbeddingModel["BlogPost"]]]
```

### Advanced Configuration

The VectorizerField supports comprehensive configuration options:

```python
from pgai.extensions import (
    EmbeddingConfig,
    ChunkingConfig,
    DiskANNIndexingConfig,
    SchedulingConfig,
    ProcessingConfig
)

class BlogPost(DeclarativeBase):
    content_embeddings = VectorizerField(
        source_column="content",
        embedding=EmbeddingConfig(
            model="text-embedding-3-small",
            dimensions=768,
            chat_user="custom_user",
            api_key_name="custom_key"
        ),
        chunking=ChunkingConfig(
            chunk_column="content",
            chunk_size=500,
            chunk_overlap=50,
            separator=" ",
            is_separator_regex=True
        ),
        indexing=DiskANNIndexingConfig(
            min_rows=10000,
            storage_layout="memory_optimized"
        ),
        formatting_template="Title: ${title}\nContent: ${chunk}",
        scheduling=SchedulingConfig(
            schedule_interval="1h",
            timezone="UTC"
        ),
        target_schema="public",
        target_table="blog_embeddings",
        view_schema="public",
        view_name="blog_embeddings_view"
    )
```

# Alembic Integration 

pgai provides Alembic operations for managing vectorizers in your database migrations.

## Manual Migration Operations

### Creating a Vectorizer

Basic creation:

```python
from alembic import op
from pgai.extensions import EmbeddingConfig, ChunkingConfig

def upgrade():
    op.create_vectorizer(
        'blog_posts',
        embedding=EmbeddingConfig(
            model='text-embedding-3-small',
            dimensions=768
        ),
        chunking=ChunkingConfig(
            chunk_column='content',
            chunk_size=700
        ),
        formatting_template='Title: ${title}\nContent: ${chunk}'
    )
```

### Dropping a Vectorizer

```python
def downgrade():
    # Drop by ID
    op.drop_vectorizer(1, drop_objects=True)
```

The `drop_objects=True` parameter will also clean up associated database objects like tables and views.

## Autogeneration Support

pgai extends Alembic's migration autogeneration to detect changes in vectorizer configurations.

### Setup

Configure your env.py to support vectorizer autogeneration:

```python
from alembic import context
from pgai.extensions.alembic.autogenerate import compare_vectorizers
from pgai.extensions.alembic.operations import CreateVectorizerOp, DropVectorizerOp

# Make sure your env.py includes:
def run_migrations_online():
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=lambda obj, name, type_, reflected, compare_to: 
                not obj.info.get("pgai_managed", False)
        )
```

### Features

The autogeneration system will:

1. Detect new vectorizers defined in models and generate creation operations
2. Detect removed vectorizers and generate drop operations
3. Detect changes in vectorizer configuration and generate update operations (as drop + create)

Example generated migration for a new vectorizer:

```python
def upgrade():
    op.create_vectorizer(
        'blog_posts',
        embedding=EmbeddingConfig(
            model='text-embedding-3-small',
            dimensions=768
        ),
        chunking=ChunkingConfig(
            chunk_column='content',
            chunk_size=500
        )
    )

def downgrade():
    op.drop_vectorizer(1)
```

When changes are made to a model's vectorizer configuration, the autogeneration will create appropriate migration operations:

```python
def upgrade():
    # Update vectorizer configuration
    op.drop_vectorizer(1, drop_objects=True)
    op.create_vectorizer(
        'blog_posts',
        embedding=EmbeddingConfig(
            model='text-embedding-3-large',  # Changed model
            dimensions=1536                  # Changed dimensions
        ),
        chunking=ChunkingConfig(
            chunk_column='content',
            chunk_size=500
        )
    )
```