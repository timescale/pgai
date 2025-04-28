# Document embeddings in pgai

This is a comprehensive walkthrough of how embedding generation for documents work in pgai. If you want to get started quickly check out the [runnable example](/examples/embeddings_from_documents).

## Introduction

While RAG (Retrieval Augmented Generation) applications typically require text data, real-world scenarios often involve documents that:

- Are stored in external systems like S3 or local filesystems
- Come in various formats (PDF, DOCX, XLSX, EPUB, etc.)
- Change frequently, requiring synchronization between sources and embeddings

pgai's document vectorization system supports directly embedding documents via a declarative approach that handles loading, parsing, chunking, and embedding files.

## Setting up document storage

### The document table

The foundation of document management in pgai is a document metadata table in PostgreSQL. Documents can either be stored directly within a table using a BYTEA column, or alternatively, the table can hold URIs pointing to files located in an external storage system such as S3. You can also include any additional metadata required by your application in this table.  
If your application already handles documents, it's likely that you already have such a table which can be used as a source for the vectorizer.

#### Minimal document table

A minimal document source table requires only an identifier and a URI pointing to the document, this can be the same column:

```sql
CREATE TABLE document (
    uri TEXT PRIMARY KEY
);

-- Example records
INSERT INTO document (uri) VALUES 
    ('s3://my-bucket/documents/product-manual.pdf'),
    ('s3://my-bucket/documents/api-reference.md'),
```

#### Extended document table

For real applications, you will often want to include additional metadata that you might need to filter or classify documents. To facilitate synchronization, consider including `created_at` and `updated_at` updates to these fields will then trigger the re-embedding process:

```sql
CREATE TABLE document (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    uri TEXT NOT NULL,
    content_type TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    owner_id INTEGER,
    access_level TEXT,
    tags TEXT[]
);

-- Example with rich metadata
INSERT INTO document (title, uri, content_type, owner_id, access_level, tags) VALUES
    ('Product Manual', 's3://my-bucket/documents/product-manual.pdf', 'application/pdf', 12, 'internal', ARRAY['product', 'reference']),
    ('API Reference', 's3://my-bucket/documents/api-reference.md', 'text/markdown', 8, 'public', ARRAY['api', 'developer']);
```

#### Storing document content directly

For smaller documents or systems without external storage, you can also store content directly as binary data:

```sql
CREATE TABLE document (
    id SERIAL PRIMARY KEY,
    file BYTEA
);

-- Example of inserting a binary document
INSERT INTO document (file) VALUES (pg_read_binary_file('/tmp/sample.pdf')::bytea);
```

## Configuring document vectorizers

A vectorizer is a declarative configuration that defines how documents are processed, chunked, and embedded. pgai's vectorizer system automatically keeps document embeddings in sync with source documents. You can find the reference for vectorizers in the [API Reference documentation](./api-reference.md).

### Example vectorizer configuration

Here's a complete vectorizer configuration for documents stored in S3:

```sql
SELECT ai.create_vectorizer(
    'document'::regclass,
    loading => ai.loading_uri(column_name => 'uri'),
    parsing => ai.parsing_auto(), -- Optional: auto-detects parser, this is the default and can also be omitted
    chunking => ai.chunking_recursive_character_text_splitter(
        chunk_size => 700,
        separators => array[E'\n## ', E'\n### ', E'\n#### ', E'\n- ', E'\n1. ', E'\n\n', E'\n', '.', '?', '!', ' ', '', '|']
    ),
    embedding => ai.embedding_openai('text-embedding-3-small', 768),
    destination => ai.destination_table('document_embeddings')
);
```

This configuration:
1. Uses the `document` table as the source
2. Loads documents from URIs in the `uri` column
3. Automatically detects and parses document formats
4. Splits text into chunks at common markdown breaking points (headers, paragraphs, etc.)
5. Generates embeddings using OpenAI's `text-embedding-3-small` model

### Explanation of the components

#### Loading

pgai supports two main loading methods:

**1. Loading from URI columns (`ai.loading_uri`)**

```sql
loading => ai.loading_uri(
    column_name => 'uri',
    retries => 6,              -- Optional: number of retry attempts (default: 6)
    aws_role_arn => 'arn:aws:iam::123456789012:role/S3AccessRole'  -- Optional: for S3 access using role assumption
)
```

This is what you will usually use to load any kind of document. It allows to download documents from:
- S3 URLs (e.g. `s3://bucket/path/to/file.pdf`)
- HTTP/HTTPS URLs (e.g. `https://example.com/file.pdf`)
- Local files on the worker machine (e.g. `/path/to/file.pdf`)

Timescale Cloud and a self-hosted pgai installation support S3 URLs out of the box. Check the [S3 documentation](./s3-documents.md) for more information on how to authenticate and configure S3.

**Other storage options:** We use the [smart_open](https://pypi.org/project/smart-open/) library to connect to the URI. That means any URI that can work with smart_open should work (including Google Cloud, Azure, etc.); however, only AWS S3 is supported on Timescale Cloud. In a self-hosted installation, other provider should work but you need to install the appropriate smart_open dependencies, and test it yourself. See the [smart-open documentation](https://pypi.org/project/smart-open/) for details.


**2. Loading from BYTEA columns (`ai.loading_column`)**

```sql
loading => ai.loading_column(
    column_name => 'content'
)
```

Alternatively you can use `loading_column` to load documents directly from a BYTEA column. This is useful if you already have the document content in your database and don't want to use any kind of external storage.

#### Parsing

To make documents LLM-friendly, you need to parse them into markdown. pgai currently supports two different parsers: pymupdf and docling. You wont have to worry about this most of the time as `ai.parsing_auto` will automatically select the appropriate parser based on the file type, but you can also explicitly select it.


You can find more information about the parsers in the [parsing reference](./api-reference.md#parsing-configuration).

#### Chunking

Chunking divides documents into smaller pieces for embedding. Since the contents gets parsed to markdown you will want to use a splitter that respects the markdown structure e.g. a setup like this:

```sql
chunking => ai.chunking_recursive_character_text_splitter(
    chunk_size => 700,
    chunk_overlap => 150,
    separators => array[
        E'\n## ',      -- Split on header level 2
        E'\n### ',     -- Split on header level 3
        E'\n#### ',    -- Split on header level 4
        E'\n- ',       -- Split on list items
        E'\n1. ',      -- Split on numbered list items
        E'\n\n',       -- Split on paragraphs
        E'\n',         -- Split on lines
        '.',           -- Split on sentences
        '?', '!',      -- Split on question/exclamation
    ]
)
```

This configuration progressively tries more granular separators to achieve the target chunk size, preserving document structure where possible.

For more information about chunking, see the [chunking reference](./api-reference.md#chunking-configuration).

#### Embedding

pgai support a wide range of embedding providers. You can find the reference for the embedding providers in the [embedding documentation](./api-reference.md#embedding-configuration).

The embedding providers all follow a similar pattern, e.g. this is how you would use the OpenAI embedding provider:
**OpenAI**

```sql
embedding => ai.embedding_openai(
    'text-embedding-3-small',  -- Model name
    768                        -- Embedding dimensions
)
```

### More examples

#### Document processing from S3 with OpenAI embeddings

```sql
-- Create document table
CREATE TABLE documentation (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    file_uri TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Add documents
INSERT INTO documentation (title, file_uri) VALUES
('Product Manual', 's3://company-docs/manuals/product-v2.pdf'),
('API Reference', 's3://company-docs/api/reference.md');

-- Create vectorizer
SELECT ai.create_vectorizer(
    'documentation'::regclass,
    loading => ai.loading_uri(column_name => 'file_uri'),
    parsing => ai.parsing_auto(), -- Auto-detects parser, this is the default and can also be omitted
    chunking => ai.chunking_recursive_character_text_splitter(
        chunk_size => 700,
        separators => array[E'\n## ', E'\n### ', E'\n#### ', E'\n- ', E'\n1. ', E'\n\n', E'\n', '.', '?', '!', ' ', '', '|']
    ),
    embedding => ai.embedding_openai('text-embedding-3-small', 768)     
);
```

#### Binary documents with ollama embeddings

```sql
-- Create document table with binary storage
CREATE TABLE internal_document (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content BYTEA NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Add documents
INSERT INTO internal_document (title, content) VALUES
('Internal Report', pg_read_binary_file('/path/to/report.pdf')::bytea),
('Internal Memo', pg_read_binary_file('/path/to/memo.docx')::bytea);

-- Create vectorizer
SELECT ai.create_vectorizer(
    'internal_document'::regclass,
    loading => ai.loading_column(column_name => 'content'),
    chunking => ai.chunking_recursive_character_text_splitter(
        chunk_size => 500,
        chunk_overlap => 100,
        separators => array[E'\n\n', E'\n', '.', ' ', '']
    ),
    embedding => ai.embedding_ollama('nomic-embed-text', 768, base_url => 'http://ollama:11434')
);
```

## Working with document embeddings

Once your vectorizer is created, pgai automatically generates a target table with your embeddings.

### Query document embeddings

To search for similar documents:

```sql
-- Basic similarity search
SELECT d.title, e.chunk, e.embedding <=> <search_embedding> AS distance
FROM document_embeddings e
JOIN documentation d ON e.id = d.id
ORDER BY distance
LIMIT 5;
```

### Combine vector similarity with metadata filters

One of the most powerful features of pgai's document approach is the ability to combine vector similarity with traditional SQL filters:

```sql
-- Find recent documentation about configuration
SELECT d.title, e.chunk
FROM document_embeddings e
JOIN documentation d ON e.id = d.id
WHERE 
    d.updated_at > (CURRENT_DATE - INTERVAL '30 days')
    AND d.title ILIKE '%configuration%'
ORDER BY e.embedding <=> <search_embedding>
LIMIT 5;
```

### Advanced query patterns

**Join with application data:**

```sql
-- Find documents relevant to customers with pending support tickets
SELECT c.name, d.title, e.chunk 
FROM customers c
JOIN support_tickets t ON c.id = t.customer_id
JOIN customer_documentation cd ON c.id = cd.customer_id
JOIN documentation d ON cd.document_id = d.id
JOIN document_embeddings e ON d.id = e.id
WHERE t.status = 'pending'
ORDER BY e.embedding <=> <search_embedding>
LIMIT 10;
```


## Monitoring and Troubleshooting

### Monitoring failures and retries

You can use the usual vectorizer monitoring tools to check the status of your vectorizers:

**Check pending items**:

```sql
select * from ai.vectorizer_status:
```

**Check for failed items**:

```sql
-- View all vectorizer errors
SELECT * FROM ai.vectorizer_errors;

-- View errors for a specific vectorizer
SELECT * FROM ai.vectorizer_errors WHERE id = <vectorizer_id>;
```
The error table includes detailed information about what went wrong.

**Check the queue and retry counts**:

```sql
SELECT * FROM ai._vectorizer_q_1
```

The queue name can be found in the `ai.vectorizer` table


## Common issues and solutions


**Embedding API rate limits**

If you encounter rate limits with your embedding provider:
- Adjust the processing batch size and concurrency explained in the [processing reference](./api-reference.md#processing-configuration) in general we recommend a low batch size (e.g. 1) and a high concurrency (e.g. 10) for documents. Since parsing takes some time.
- Consider upgrading API tiers or using a different provider

**Document limitations**
- The pgai document vectorizer is designed for small to medium sized documents. Large documents will take a long time to be parsed and embedded. The page limit for pdfs on Timescale Cloud is ~50 pages. For larger documents consider splitting them into smaller chunks.
- Supported documents depend on the parser that you are using. Check the [parser reference](./api-reference.md#parsing-configuration) to see what types of documents are supported by the parser you are using.
