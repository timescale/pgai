# Automate AI embedding with pgai Vectorizer

Vector embeddings transform text and documents into compact, semantically rich representations that enable context-aware searches beyond traditional keyword matching.

While PostgreSQL excels at storing and querying these embeddings, synchronizing embeddings with source data has traditionally required custom solutions from developers.

pgai Vectorizer provides a SQL-level interface that automates the embedding process within your database. By treating embeddings as a declarative feature—similar to an index—we simplify the entire workflow.

With pgai Vectorizer, you can:

- Designate text columns or documents for embedding using customizable rules
- Automatically generate and maintain searchable embedding tables 
- Keep embeddings synchronized with source data (asynchronously)
- Access a view that joins base tables with their embeddings

This page provides an overview of Vectorizer features. For quick setup instructions, see the 
[Vectorizer quick start](/docs/vectorizer/quick-start.md). For technical details, see the
[Vectorizer API reference](/docs/vectorizer/api-reference.md).

Vectorizer uses a background worker for embedding generation, making the process performant and resilient to LLM endpoint failures. On [Timescale Cloud](https://tsdb.co/gh-pgai-signup), the worker runs automatically. For other cloud providers (AWS RDS, Supabase, etc.) or self-hosted Postgres, use the [vectorizer worker](/docs/vectorizer/worker.md) to process your vectorizers.

## How vectorizer works

The vectorizer is designed to be flexible and customizable. Each vectorizer defines a pipeline for creating embeddings from your data. The pipeline consists of these components:

- **[Loading](/docs/vectorizer/api-reference.md#loading-configuration):** Defines the source of data to embed - either directly from a database column or from an external file via URI
- **[Parsing](/docs/vectorizer/api-reference.md#parsing-configuration):** Converts non-text documents (PDF, HTML, markdown) into a text format suitable for embedding
- **[Chunking](/docs/vectorizer/api-reference.md#chunking-configuration):** Splits text data into smaller, semantically meaningful pieces
- **[Formatting](/docs/vectorizer/api-reference.md#formatting-configuration):** Prepares each chunk for embedding, optionally adding context like document title or metadata
- **[Embedding](/docs/vectorizer/api-reference.md#embedding-configuration):** Generates vector embeddings using your chosen LLM provider and model

Let's explore how the Vectorizer can transform your approach to unstructured data analysis and semantic search:

- [Select an embedding provider and set up your API Keys](#select-an-embedding-provider-and-set-up-your-api-keys)
- [Define a vectorizer](#define-a-vectorizer)
  - [Text column embedding](#text-column-embedding)
  - [Document embedding](#document-embedding)
- [Query an embedding](#query-an-embedding)
- [Inject context into vectorizer chunks](#inject-context-into-vectorizer-chunks)
- [Improve query performance on your Vectorizer](#improve-query-performance-on-your-vectorizer)
- [Control vectorizer run time](#control-the-vectorizer-run-time-)
- [The embedding storage table](#the-embedding-storage-table)
- [Destination Options for Embeddings](#destination-options-for-embeddings)
- [Monitor a vectorizer](#monitor-a-vectorizer)
- [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)

## Select an embedding provider and set up your API Keys

Vectorizer supports the following vector embedding providers as first-party integrations:
- [Ollama](https://ollama.com/)
- [Voyage AI](https://www.voyageai.com/)
- [OpenAI](https://openai.com/)

Additionally, through the [LiteLLM](https://litellm.ai) provider we support:
- [Cohere](https://cohere.com/)
- [HuggingFace Inference Endpoints](https://endpoints.huggingface.co/)
- [Mistral](https://mistral.ai/)
- [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
- [AWS Bedrock](https://aws.amazon.com/bedrock/)
- [Vertex AI](https://cloud.google.com/vertex-ai)

When using an external embedding service, you need to setup your API keys to access
the service. To store several API keys, you give each key a name and reference them
in the `embedding` section of the Vectorizer configuration. The default API key
names match the embedding provider's default name.

The default key names are:

| Provider  | Key name       |
|-----------|----------------|
| OpenAI    | OPENAI_API_KEY |
| Voyage AI | VOYAGE_API_KEY |

Setting up your API keys is done differently depending on whether you are using Vectorizer in
Timescale Cloud or on a self-hosted Postgres server.

- Timescale Cloud

  1. In [Timescale Console > Project Settings](https://console.cloud.timescale.com/dashboard/settings), click `AI Model API Keys`.
  1. Click `Add AI Model API Keys`, add your key, then click `Add API key`.

  Your API key is stored securely in Timescale Cloud, not your database.

- Self-hosted Postgres

  Set an environment variable that is the [same as your API key name](/docs/vectorizer/worker.md#install-and-configure-vectorizer-worker). 
  For example:
  ```bash
  export OPENAI_API_KEY="Your OpenAI API key"
  ```

## Define a vectorizer

pgai supports two main types of data sources for vectorizing:
1. [Text column embedding](#text-column-embedding) - for embedding text stored directly in database columns
2. [Document embedding](#document-embedding) - for embedding files stored either as binary data or referenced by URI

### Text column embedding

You can configure the system to automatically generate and update embeddings
for a table's text data. Let's consider the following example table:

```sql
CREATE TABLE blog(
    id        SERIAL PRIMARY KEY,
    title     TEXT,
    authors   TEXT,
    contents  TEXT,
    metadata  JSONB 
);
```

To configure the system to embed this data automatically, you can use a SQL
query like this:

```sql
SELECT ai.create_vectorizer( 
   'blog'::regclass,
   name => 'blog_embeddings',  -- Optional custom name for easier reference
   loading => ai.loading_column('contents'),
   embedding => ai.embedding_ollama('nomic-embed-text', 768),
   destination => ai.destination_table('blog_contents_embeddings')
);
```

This example uses the `nomic-embed-text` embedding model hosted on a local
Ollama instance. Vectorizer supports other embedding providers, for more details
consult the [embedding configuration](/docs/vectorizer/api-reference.md#embedding-configuration)
section of the vectorizer API reference.

The `loading` parameter specifies the source of the data to generate embeddings from. In this case, we're using the `contents` column as our source.

Additionally, if the `contents` field is lengthy, it is split into multiple chunks,
resulting in several embeddings for a single blog post. Chunking helps
ensure that each embedding is semantically coherent, typically representing a
single thought or concept. A useful mental model is to think of embedding one
paragraph at a time.

### Document embedding

For embedding documents (like PDFs, Word documents, markdown files, etc.), the workflow is slightly different. You'll first need to set up a document table and then create a vectorizer that points to this table.

If you want to get started quickly, check out the [runnable example](/examples/embeddings_from_documents).

If you are storing documents in AWS S3, you can use the [S3 documentation](s3-documents.md) to learn more about how to configure S3 for document storage and synchronize your S3 buckets with your document table.

#### Introduction to document embeddings

While RAG (Retrieval Augmented Generation) applications typically require text data, real-world scenarios often involve documents that:

- Are stored in external systems like S3 or local filesystems
- Come in various formats (PDF, DOCX, XLSX, EPUB, etc.)
- Change frequently, requiring synchronization between sources and embeddings

pgai's document vectorization system supports directly embedding documents via a declarative approach that handles loading, parsing, chunking, and embedding files.

#### Setting up document storage

The foundation of document management is a table in PostgreSQL that stores document metadata. Documents can either be stored directly using a BYTEA column, or alternatively, the table can hold URIs pointing to files located in an external storage system such as S3.

If your application already handles documents, it's likely that you already have such a table which can be used as a source for the vectorizer. If you don't have such a table yet and are storing documents in S3 we have a [guide on how to sync S3 to a document table](s3-documents.md#syncing-s3-to-a-documents-table).

**Minimal document table with URIs:**

```sql
CREATE TABLE document (
    uri TEXT PRIMARY KEY,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Example records
INSERT INTO document (uri) VALUES 
    ('s3://my-bucket/documents/product-manual.pdf'),
    ('s3://my-bucket/documents/api-reference.md');
```

**Extended document table with metadata:**

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
```

**Storing document content directly:**

```sql
CREATE TABLE document (
    id SERIAL PRIMARY KEY,
    file BYTEA,
    title TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Example of inserting a binary document
INSERT INTO document (title, file) VALUES 
    ('Sample Document', pg_read_binary_file('/tmp/sample.pdf')::bytea);
```

#### Creating a document vectorizer

Here's an example vectorizer configuration for documents stored in S3:

```sql
SELECT ai.create_vectorizer(
    'documentation'::regclass,
    loading => ai.loading_uri(column_name => 'file_uri'),
    parsing => ai.parsing_auto(), -- Auto-detects parser based on file type, this is the default and can also be omitted
    chunking => ai.chunking_recursive_character_text_splitter(
        chunk_size => 700,
        separators => array[E'\n## ', E'\n### ', E'\n#### ', E'\n- ', E'\n1. ', E'\n\n', E'\n', '.', '?', '!', ' ', '', '|']
    ),
    embedding => ai.embedding_ollama('nomic-embed-text', 768)     
);
```

For documents stored directly in the database:

```sql
SELECT ai.create_vectorizer(
    'document'::regclass,
    loading => ai.loading_column(column_name => 'file'),
    parsing => ai.parsing_auto(),
    chunking => ai.chunking_recursive_character_text_splitter(
        chunk_size => 700,
        chunk_overlap => 150,
        separators => array[E'\n## ', E'\n### ', E'\n#### ', E'\n- ', E'\n1. ', E'\n\n', E'\n', '.', '?', '!', ' ', '', '|']
    ),
    embedding => ai.embedding_ollama('nomic-embed-text', 768),
    destination => ai.destination_table('document_embeddings')
);
```

#### Explanation of document vectorizer components

##### Loading documents

pgai supports loading documents from references to external storage systems using the `ai.loading_uri` function or from a BYTEA column using the `ai.loading_column` function.

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

**Storing documents in AWS S3**: Timescale Cloud and a self-hosted pgai installation support AWS S3 URLs out of the box. Check the [S3 documentation](./s3-documents.md) for more information on how to authenticate and configure S3.

**Other storage options:** We use the [smart_open](https://pypi.org/project/smart-open/) library to connect to the URI. That means any URI that can work with smart_open should work (including Google Cloud, Azure, etc.); however, only AWS S3 is supported on Timescale Cloud. In a self-hosted installation, other providers should work but you need to install the appropriate smart_open dependencies and test it yourself. See the [smart-open documentation](https://pypi.org/project/smart-open/) for details.

**2. Loading from BYTEA columns (`ai.loading_column`)**

For documents stored directly in a BYTEA column:

```sql
loading => ai.loading_column(
    column_name => 'file'
)
```

This is useful if you already have the document content in your database and don't want to use any kind of external storage.

##### Parsing documents

To make documents LLM-friendly, you need to parse them into markdown. pgai currently supports two different parsers: pymupdf and docling. You won't have to worry about this most of the time as `ai.parsing_auto` will automatically select the appropriate parser based on the file type, but you can also explicitly select it.

You can find more information about the parsers in the [parsing reference](./api-reference.md#parsing-configuration).

##### Chunking documents

Chunking divides documents into smaller pieces for embedding. Since the content gets parsed to markdown, you will want to use a splitter that respects the markdown structure, for example:

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

For more details on document vectorization, including supported document types and configuration options, see the [Document Embeddings documentation](document-embeddings.md).

## Query an embedding

The `create_vectorizer` command generates a view with the same name as the
specified destination. This view contains all the embeddings for the table.
Note that you'll typically have multiple rows in the view for each entry,
as multiple embeddings are usually generated for each source document or text field.

The view includes all columns from the source table plus the following additional columns:

| Column         | Type   | Description                                                     |
|----------------|--------|-----------------------------------------------------------------|
| embedding_uuid | UUID   | Unique identifier for the embedding                             |
| chunk          | TEXT   | The text segment that was embedded                              |
| embedding      | VECTOR | The vector representation of the chunk                          |
| chunk_seq      | INT    | Sequence number of the chunk within the document, starting at 0 |


To find the closest embeddings to a query, use this canonical SQL query:

```sql
SELECT 
   chunk,
   embedding <=> <query embedding> as distance
FROM blog_contents_embeddings
ORDER BY distance
LIMIT 10;
```

 The `<=>` operator calculates the distance between the query embedding and each
row's embedding vector. This is a simple way to do semantic search.

**Tip**: You can use the `ai.ollama_embed` function in our [PostgreSQL extension](/projects/extension/README.md) to generate an embedding for a user-provided query right inside the database.

You can combine this with metadata filters by adding a WHERE clause:

```sql
SELECT 
   chunk,
   embedding <=> <query embedding> as distance
FROM blog_contents_embeddings
WHERE 
   metadata->>'department' = 'finance'
ORDER BY 
   distance 
LIMIT 10;
```

This approach works with any column from the original table. For example, to search by author:

```sql
SELECT 
   chunk,
   embedding <=> <query embedding> as distance,
   author
FROM blog_contents_embeddings       
WHERE 
   author = 'Bulgakov'    
ORDER BY 
   distance 
LIMIT 10;
```

### Advanced query patterns with document embeddings

You can create more sophisticated queries by combining vector similarity with traditional SQL features:

**Combining vector similarity with metadata filters:**

```sql
-- Find recent documentation about configuration
SELECT title, chunk
FROM document_embeddings
WHERE 
    updated_at > (CURRENT_DATE - INTERVAL '30 days')
    AND title ILIKE '%configuration%'
ORDER BY embedding <=> <search_embedding>
LIMIT 5;
```

**Joining with application data:**

```sql
-- Find documents relevant to customers with pending support tickets
SELECT c.name, d.title, e.chunk 
FROM customers c
JOIN support_tickets t ON c.id = t.customer_id
JOIN customer_documentation cd ON c.id = cd.customer_id
JOIN document_embeddings e ON cd.document_id = e.id
WHERE t.status = 'pending'
ORDER BY e.embedding <=> <search_embedding>
LIMIT 10;
```

## Inject context into vectorizer chunks

However, splitting text into chunks can sometimes lead to losing context. To
mitigate this, you can reintroduce context into each chunk. For instance, you
might want to repeat the blog post's title in every chunk. This is easily
achieved using the `formatting` parameter, which allows you to inject row data
into each chunk:

```sql
SELECT ai.create_vectorizer(   
    'blog'::regclass,
    loading => ai.loading_column('contents'),
    embedding => ai.embedding_ollama('nomic-embed-text', 768),
    formatting => ai.formatting_python_template('$title: $chunk'),
    destination => ai.destination_table('blog_contents_embeddings')
);
```

This approach ensures that each chunk retains important contextual information,
improving the quality and relevance of the embeddings.

Formatting allows you to inject additional information into each chunk. This is
needed because splitting the text into chunks can lead to losing important
context. For instance, you might want to include the authors and title with each
chunk. This is achieved using Python template strings, which have access to all
columns in the row and a special `$chunk` variable containing the chunk's text.

You may need to reduce the chunk size to ensure the formatted text fits within
token limits. Adjust the `chunk_size` parameter of the text_splitter
accordingly:

```sql
SELECT ai.create_vectorizer(
    'blog'::regclass,
    loading => ai.loading_column('contents'),
    embedding => ai.embedding_ollama('nomic-embed-text', 768),
    formatting => ai.formatting_python_template('$title - by $author - $chunk'),
    destination => ai.destination_table('blog_contents_embeddings')
);
```

The default format string is simply `$chunk`.

## Improve query performance on your Vectorizer

A vector index on the embedding column improves query performance. On Timescale Cloud, a vectorscale
index is automatically created after 100,000 rows of vector data are present.
This behaviour is configurable, you can also specify other vector index types. The following
example uses a HNSW index:


```sql
SELECT ai.create_vectorizer(
    'blog'::regclass,
    loading => ai.loading_column('contents'),
    embedding => ai.embedding_ollama('nomic-embed-text', 768),
    formatting => ai.formatting_python_template('$title - by $author - $chunk'),
    indexing => ai.indexing_hnsw(min_rows => 100000, opclass => 'vector_l2_ops'),
    destination => ai.destination_table('blog_contents_embeddings')
);
```

Note: Indexing relies on a background job that runs periodically, so this
feature will not work if scheduling is disabled (which is the default for self-hosted installations).

## Control the vectorizer run time 

When you use Vectorizer on Timescale Cloud, you use scheduling to control the time when vectorizers run.
A scheduled job checks for work to be done and, if so, runs the cloud function to embed the data.
By default, scheduling uses TimescaleDB background jobs running every five minutes.
Once the table is large enough, scheduling also handles index creation on the embedding column. 

When you self-host vectorizer, the vectorizer worker uses a polling mechanism to check whether
there is work to be done. Thus, scheduling is not needed and is deactivated by default.

Note: when scheduling is disabled, the index is not created automatically. You need to create it manually.

## The embedding storage table

The view is based on a table storing embeddings, named
`blog_contents_embeddings_store`. You can query this table directly for
potentially more efficient queries. The table structure is as follows:

```sql
CREATE TABLE blog_contents_embeddings_store(
    embedding_uuid UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),     
    id INT,  -- primary key referencing the blog table
    chunk_seq INT NOT NULL, 
    chunk TEXT NOT NULL,
    embedding VECTOR(768) NOT NULL,
    UNIQUE (id, chunk_seq),
    FOREIGN KEY (id) REFERENCES public.blog(id) ON DELETE CASCADE
);
```

## Destination Options for Embeddings

Vectorizer supports two different ways to store your embeddings. You should choose the option to use based on whether:
-  You need **multiple embeddings per source row** because of chunking. This is the common case. You should choose table destination.
-  You need a **single embedding per source row**. This happens if you are either embedding small text fragments (e.g. a single sentence) or if have already chunked the document and the souce table contains the chunks. In this case, you should choose a column destination.

### 1. Table Destination (Default)

The default approach creates a separate table to store embeddings and a view that joins with the source table:

```sql
SELECT ai.create_vectorizer(
    'blog'::regclass,
    name => 'blog_vectorizer',  -- Optional custom name for easier reference
    loading => ai.loading_column('contents'),
    embedding => ai.embedding_ollama('nomic-embed-text', 768),
    destination => ai.destination_table(
        target_schema => 'public',
        target_table => 'blog_embeddings_store',
        view_name => 'blog_embeddings'
    ),
);
```

**When to use table destination:**
- When you need multiple embeddings per row (chunking)
- For large text fields that need to be split
- You are vectorizing documents (which typically require chunking)

### 2. Column Destination

For simpler cases, you can add an embedding column directly to the source table. This can only be used when the vectorizer does not perform chunking because it requires a one-to-one relationship between the source data and the embedding. This is useful in cases where you know the source text is short (as is common if the chunking has already been done upstream in your data pipeline).

The workflow is that your application inserts data into the table with a NULL in the embedding column. The vectorizer will then read the row, generate the embedding and update the row with the correct value in the embedding column.
```sql
SELECT ai.create_vectorizer(
    'product_descriptions'::regclass,
    name => 'product_descriptions_vectorizer',
    loading => ai.loading_column('description'),
    embedding => ai.embedding_ollama('nomic-embed-text', 768),
    chunking => ai.chunking_none(),  -- Required for column destination
    destination => ai.destination_column('description_embedding')
);
```

**When to use column destination:**
- When you need exactly one embedding per row
- For shorter text that doesn't require chunking
- When your application already takes care of the chunking before inserting into the database
- When you want to avoid creating additional database objects

**Note:** Column destination requires chunking to be set to `ai.chunking_none()` since it can only store one embedding per row.

## Monitor a vectorizer

Since embeddings are created asynchronously, a delay may occur before they
become available. Use the `vectorizer_status` view to monitor the vectorizer's
status:

```sql
SELECT * FROM ai.vectorizer_status;
```

Sample output:

| id | source_table | target_table                         | view                            | pending_items |
|----|--------------|--------------------------------------|---------------------------------|---------------|
| 1  | public.blog  | public.blog_contents_embeddings_store | public.blog_contents_embeddings | 1             |

The `pending_items` column indicates the number of items still awaiting embedding creation.
If the number of pending items exceeds 10,000, we return the maximum value of a bigint (`9223372036854775807`)
instead of exhaustively counting the items. This is done for performance.

Alternately, you can call the `ai.vectorizer_queue_pending` function to get the count of pending items
for a single vectorizer. The `exact_count` parameter is defaulted to `false`, but passing `true`
will exhaustively count the exact number of pending items.

```sql
select ai.vectorizer_queue_pending(1, exact_count=>true);
```

## Monitoring and Troubleshooting

### Checking for failed items

```sql
-- View all vectorizer errors
SELECT * FROM ai.vectorizer_errors;

-- View errors for a specific vectorizer
SELECT * FROM ai.vectorizer_errors WHERE id = <vectorizer_id>;
```
The error table includes detailed information about what went wrong.

### Checking the queue and retry counts

```sql
SELECT * FROM ai._vectorizer_q_1
```

The queue name can be found in the `ai.vectorizer` table

### Common issues and solutions

**Embedding API rate limits**

If you encounter rate limits with your embedding provider:
- Adjust the processing batch size and concurrency explained in the [processing reference](./api-reference.md#processing-configuration) in general we recommend a low batch size (e.g. 1) and a high concurrency (e.g. 10) for documents. Since parsing takes some time.
- Consider upgrading API tiers or using a different provider

**Document limitations**
- The pgai document vectorizer is designed for small to medium sized documents. Large documents will take a long time to be parsed and embedded. The page limit for pdfs on Timescale Cloud is ~50 pages. For larger documents consider splitting them into smaller chunks.
- Supported documents depend on the parser that you are using. Check the [parser reference](./api-reference.md#parsing-configuration) to see what types of documents are supported by the parser you are using.

## Appendix: More example vectorizer configurations

### Document processing from S3 with Ollama embeddings

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
    embedding => ai.embedding_ollama('nomic-embed-text', 768)     
);
```

### Binary documents with ollama embeddings

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