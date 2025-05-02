# Automate AI embedding with pgai Vectorizer

Vectorizer transforms how you create and manage semantic embeddings within your database, making it easy to vectorize content for semantic search and text analysis. This guide explains the vectorizer pipeline and workflow.

**New to vector embeddings?** Check out the [Concepts page](concepts.md) for a primer on embeddings and their applications.

## The Vectorizer Pipeline

![Vectorizer Architecture](/docs/images/pgai_architecture.png)

The pgai vectorizer follows a data transformation pipeline that processes your content through these stages:

1. **Loading**: Retrieves data from your source (text columns or documents)
2. **Parsing** (document-specific): Converts documents into a consistent text format 
3. **Chunking**: Breaks text into semantically meaningful segments
4. **Formatting**: Enhances chunks with additional context
5. **Embedding**: Transforms text into vector representations
6. **Storage**: Saves embeddings with links back to source

Each component can be configured to suit your specific requirements. For detailed options for each pipeline component, see the [API Reference](api-reference.md).

## Implementation Guides

Based on your data source, you'll use different approaches to create embeddings:

- [Column Embeddings Guide](column-embeddings.md) - For text data in database tables
- [Document Embeddings Guide](document-embeddings.md) - For external files like PDFs

Each guide provides specialized examples and best practices for that specific use case. For conceptual understanding of these approaches, see the [Concepts](concepts.md) page.

## Quick Example

Here's a simple example of creating a vectorizer for a blog table:

```sql
-- Sample blog table
CREATE TABLE blog(
    id        SERIAL PRIMARY KEY,
    title     TEXT,
    authors   TEXT,
    contents  TEXT,
    metadata  JSONB 
);

-- Create a vectorizer
SELECT ai.create_vectorizer( 
   'blog'::regclass,
   loading => ai.loading_column('contents'),
   embedding => ai.embedding_openai('text-embedding-3-small', 1536),
   formatting => ai.formatting_python_template('$title by $authors: $chunk'),
   destination => ai.destination_table('blog_contents_embeddings')
);
```

This configuration:
1. Loads text from the `contents` column
2. Automatically chunks the content into segments
3. Formats each chunk with title and author context
4. Creates embeddings using OpenAI's model
5. Stores results in a dedicated table with a view

## Querying Embeddings

Once your vectorizer has processed the data, you can perform semantic searches:

```sql
-- Find similar content
SELECT 
   title,
   chunk,
   embedding <=> ai.openai_embed('How do I optimize database performance?', 'text-embedding-3-small') as distance
FROM blog_contents_embeddings
ORDER BY distance
LIMIT 10;
```

You can combine vector similarity with metadata filters:

```sql
-- Find similar blog posts but only in a specific category
SELECT
   title,
   chunk,
   embedding <=> ai.openai_embed('performance tips', 'text-embedding-3-small') as distance
FROM blog_contents_embeddings
WHERE
   metadata->>'category' = 'Database'
ORDER BY distance
LIMIT 5;
```

## Asynchronous Processing

pgai uses background workers to process vectorizers:

- On Timescale Cloud, workers run automatically
- For self-hosted installations, you run the [vectorizer worker](/docs/vectorizer/worker.md)
- Workers poll for pending items and process in batches
- Monitor progress through the `ai.vectorizer_status` view

```sql
-- Check vectorizer status
SELECT * FROM ai.vectorizer_status;

-- View any errors
SELECT * FROM ai.vectorizer_errors;
```

## Next Steps

- Review [Vectorizer Concepts](concepts.md) for an in-depth explanation of how vectorizers work
- Read the [Column Embeddings Guide](column-embeddings.md) for embedding database text columns
- Explore the [Document Embeddings Guide](document-embeddings.md) for working with external documents
- See the [API Reference](api-reference.md) for detailed function documentation
- Try the [Quick Start Guide](quick-start.md) for a hands-on introduction

For a detailed explanation of provider setup and advanced configuration options, refer to our [API Reference](api-reference.md).
