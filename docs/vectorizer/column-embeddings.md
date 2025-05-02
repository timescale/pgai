# Column-Based Embeddings in pgai

This guide walks you through the process of embedding text columns in existing database tables. If you're looking to embed external documents like PDFs, see our [document embeddings guide](document-embeddings.md).

## Introduction

Column-based embeddings are ideal when:
- You have text data already stored in database tables
- The text data is relatively small (paragraphs or sentences)
- You want to make existing structured data semantically searchable

pgai makes it easy to turn any text column into a searchable vector embedding with minimal configuration.

## Setting Up Your Data Source

Start with a table containing the text columns you want to embed:

```sql
CREATE TABLE blog(
    id        SERIAL PRIMARY KEY,
    title     TEXT,
    authors   TEXT,
    contents  TEXT,
    metadata  JSONB 
);

-- Add some sample data
INSERT INTO blog (title, authors, contents, metadata) 
VALUES 
('Introduction to Vector Search', 'Ana Smith', 'Vector search is a technique...', '{"category": "AI", "tags": ["search", "vectors"]}'),
('PostgreSQL Tips', 'John Doe', 'Here are some tips for optimizing...', '{"category": "Database", "tags": ["postgres", "performance"]}');
```

## Column Embedding Options

pgai offers two approaches for column embeddings, which are detailed in the [destination configuration](api-reference.md#destination-configuration) section of the API reference:

### 1. Table Destination (Multiple Embeddings Per Row)

Ideal for longer text that requires chunking:

```sql
SELECT ai.create_vectorizer( 
   'blog'::regclass,
   loading => ai.loading_column('contents'),
   embedding => ai.embedding_openai('text-embedding-3-small', 1536),
   destination => ai.destination_table('blog_contents_embeddings')
);
```

This creates:
- A separate table storing the embeddings (`blog_contents_embeddings_store`)
- A view that joins the embeddings with the original table (`blog_contents_embeddings`)
- Automatic chunking of longer text (configurable)

**When to use**: For longer text fields (paragraphs, articles) that benefit from being split into multiple chunks

### 2. Column Destination (Single Embedding Per Row)

Perfect for short text where no chunking is needed:

```sql
-- Create a table with an embedding column
CREATE TABLE product_names (
   id SERIAL PRIMARY KEY,
   name TEXT NOT NULL,
   name_embedding VECTOR(768)
);

-- Insert some data (embedding column starts as NULL)
INSERT INTO product_names (name) VALUES 
   ('Ergonomic Office Chair'),
   ('Wireless Keyboard');

-- Create vectorizer to populate embedding column
SELECT ai.create_vectorizer(
   'product_names'::regclass,
   loading => ai.loading_column('name'),
   embedding => ai.embedding_openai('text-embedding-3-small', 768),
   chunking => ai.chunking_none(),  -- Required for column destination
   destination => ai.destination_column('name_embedding')
);
```

**When to use**: For short text like titles, names, or sentences where each row needs exactly one embedding

## Enhancing Embeddings with Context

To improve embedding quality, you can inject additional context from other columns:

```sql
SELECT ai.create_vectorizer(
   'blog'::regclass,
   loading => ai.loading_column('contents'),
   embedding => ai.embedding_openai('text-embedding-3-small', 768),
   formatting => ai.formatting_python_template('$title by $authors: $chunk'),
   destination => ai.destination_table('blog_contents_embeddings')
);
```

This adds the title and authors to each chunk, providing richer context for the embedding model.

## Querying Column Embeddings

### Table Destination Queries

When using table destination, query the generated view:

```sql
-- Get a query embedding
SELECT ai.openai_embed('How to optimize PostgreSQL?', 'text-embedding-3-small') as query_embedding;

-- Find similar content
SELECT
   title,
   authors,
   chunk,
   embedding <=> '<query_embedding>' as distance
FROM blog_contents_embeddings
ORDER BY distance
LIMIT 5;
```

### Column Destination Queries

When using column destination, query the source table directly:

```sql
-- Get a query embedding
SELECT ai.openai_embed('wireless keyboard', 'text-embedding-3-small') as query_embedding;

-- Find similar products
SELECT
   name,
   name_embedding <=> '<query_embedding>' as distance
FROM product_names
ORDER BY distance
LIMIT 5;
```

## Hybrid Search with Metadata Filters

One of the major advantages of keeping embeddings in your database is the ability to combine vector similarity with traditional SQL filters:

```sql
-- Find similar blog posts but only in the Database category
SELECT
   title,
   chunk,
   embedding <=> '<query_embedding>' as distance
FROM blog_contents_embeddings
WHERE
   metadata->>'category' = 'Database'
ORDER BY distance
LIMIT 5;
```

## Performance Optimization

### Indexing

For large embedding tables, adding a vector index dramatically improves query performance:

```sql
SELECT ai.create_vectorizer(
   'blog'::regclass,
   loading => ai.loading_column('contents'),
   embedding => ai.embedding_openai('text-embedding-3-small', 768),
   indexing => ai.indexing_hnsw(min_rows => 10000),
   destination => ai.destination_table('blog_contents_embeddings')
);
```

This automatically creates a HNSW index once the table reaches 10,000 rows.

### Monitoring and Troubleshooting

Track the status of your vectorizers:

```sql
-- View all vectorizers
SELECT * FROM ai.vectorizer_status;

-- Check pending items for a specific vectorizer
SELECT ai.vectorizer_queue_pending(1);

-- View any errors
SELECT * FROM ai.vectorizer_errors WHERE id = 1;
```

## Working with SQLAlchemy

If you're using Python with SQLAlchemy, pgai provides integration tools:

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String
from pgai.sqlalchemy import vectorizer_relationship

class Product(Base):
    __tablename__ = "products"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    
    # Add vector embeddings for the description field
    description_embeddings = vectorizer_relationship(
        target_table='product_embeddings',
        dimensions=768
    )

# Query with vector similarity
def find_similar_products(query_embedding, limit=5):
    with Session(engine) as session:
        result = session.query(
            Product,
            Product.description_embeddings.embedding.cosine_distance(query_embedding).label('distance')
        ).join(Product.description_embeddings).order_by(
            'distance'
        ).limit(limit).all()
    return result
```

## Summary

Column-based embeddings provide a seamless way to make your structured data semantically searchable. By choosing the right destination type (table or column) and configuring the appropriate chunking strategy, you can optimize for your specific use case.

For more advanced configurations, see the [Vectorizer API Reference](api-reference.md).