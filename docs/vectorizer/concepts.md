# Vectorizer Concepts

This guide introduces the core concepts of pgai's Vectorizer system, helping you understand its components and how they work together to create and maintain semantic embeddings in your database.

## What are vector embeddings?

Vector embeddings are numerical representations of text that capture semantic meaning. They transform text into compact vectors where similar content has vectors that are closer together in the high-dimensional space. This enables:

- **Semantic search**: Find content based on meaning, not just keywords
- **Similarity calculations**: Measure how related different texts are
- **Clustering**: Group similar content together

## The Vectorizer Pipeline

At its core, the Vectorizer system follows a data transformation pipeline to convert unstructured text into searchable vector embeddings:

![Vectorizer Pipeline](/docs/images/pgai_architecture.png)

The pipeline consists of these key stages:

1. **Loading**: Retrieving data from source tables or external documents
2. **Parsing**: Converting documents into a consistent text format
3. **Chunking**: Breaking text into appropriately sized segments  
4. **Formatting**: Enhancing chunks with additional context
5. **Embedding**: Converting text chunks into vector representations
6. **Storage**: Saving embeddings with links back to source data

This pipeline runs asynchronously, ensuring your database remains responsive while embeddings are generated in the background.

For detailed configuration options for each pipeline component, see the [API Reference](api-reference.md).

## The Two Primary Embedding Workflows

pgai supports two main approaches to embedding generation:

### 1. Column-Based Embeddings

Ideal for existing database tables with text columns that you want to make searchable:

- **Source**: Text columns in database tables
- **Use case**: Making existing structured data semantically searchable
- **Storage**: Either in a separate table or directly in a column

See the [Column Embeddings Guide](column-embeddings.md) for implementation details.

### 2. Document-Based Embeddings

Designed for external documents like PDFs, Word files, or Markdown documents:

- **Source**: External documents from S3, URLs, or binary data
- **Use case**: Vectorizing unstructured documents for RAG applications
- **Processing**: Additional parsing to convert documents to text

See the [Document Embeddings Guide](document-embeddings.md) for implementation details.

## Core Components

### Workers and Asynchronous Processing

The Vectorizer system uses background workers to generate embeddings asynchronously:

- Vectorizers define what to embed, but don't do the work themselves
- Workers poll for pending items and process them in batches
- This ensures database performance isn't impacted by embedding generation
- On Timescale Cloud, workers run automatically
- For self-hosted installations, you need to run the [vectorizer worker](/docs/vectorizer/worker.md)

### Storage Models

pgai offers two approaches to storing embeddings, which are detailed in the [destination configuration](api-reference.md#destination-configuration) section of the API reference:

#### Table Destination (Default)

Creates a separate table for embeddings and a view that joins with the source table.

**When to use**:
- For document embeddings 
- When chunking is required
- When you need multiple embeddings per source row

#### Column Destination

Adds an embedding column directly to the source table.

**When to use**:
- For single sentence or short text embedding
- When no chunking is needed (one-to-one relationship) 
- When the source table already contains the chunks

## Understanding Embedding Operations

- **Creating**: Vectorizers are created with `ai.create_vectorizer()`
- **Monitoring**: Track status with `ai.vectorizer_status` view
- **Querying**: Use standard PostgreSQL and pgvector operations (`<=>` operator for similarity)
- **Performance**: Indexes are automatically created to optimize similarity searches

## Next Steps

- See the [Overview](/docs/vectorizer/overview.md) for a pipeline-focused walkthrough
- Explore [Column Embeddings](/docs/vectorizer/column-embeddings.md) for embedding table columns
- Read about [Document Embeddings](/docs/vectorizer/document-embeddings.md) for working with external files
- Review the [API Reference](/docs/vectorizer/api-reference.md) for detailed function documentation