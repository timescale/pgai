# Vectorizer Guide

Vector embeddings have emerged as a powerful tool for transforming text into
compact, semantically rich representations. This approach unlocks the potential
for more nuanced and context-aware searches, surpassing traditional
keyword-based methods. By leveraging vector embeddings, users can search through
things that have similar meanings but use completely different words.

While modern vector databases like PostgreSQL excel at storing and querying
these embeddings efficiently, the challenge of maintaining synchronization
between embeddings and their source data has typically fallen to developers,
requiring manual workflows and custom solutions.

Enter our innovative SQL-level interface for embedding services. This guide
introduces a groundbreaking approach that automates the embedding process within
the database management system itself. By treating embeddings as a declarative,
DDL-like feature—akin to an index -- but with the added flexibility of
representing only a part of a row's data -- we've simplified the entire workflow.

Our system empowers you to:

1. Designate any text column for embedding using customizable rules. 
1. Automatically generate and maintain searchable embedding tables. 
1. Keep embeddings continuously synchronized with source data (asynchronously).
1. Utilize a convenient view that seamlessly joins base tables with their
embeddings.

This guide offers a comprehensive overview of the Vectorizer feature,
demonstrating how it streamlines the process of working with vector embeddings
in your database. A more detailed technical specification is available
[here](./vectorizer.md).

Let's explore how the Vectorizer can transform your approach to unstructured,
textual, data analysis and semantic search.

## Basic usage of the vectorizer

### Defining the vectorizer

Users can configure the system to automatically generate and update embeddings
for a table's data. Let's consider the following example table:

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
    destination => 'blog_contents_embeddings',
    embedding => ai.embedding_openai('text-embedding-3-small', 768),
    chunking => ai.chunking_character_text_splitter('contents'),
);
```

In this example, the `contents` field is split into multiple chunks if it's
lengthy, resulting in several embeddings for a single blog post. Chunking helps
ensure that each embedding is semantically coherent, typically representing a
single thought or concept (a useful mental model is to think of embedding one
paragraph at a time).

However, splitting text into chunks can sometimes lead to a loss of context. To
mitigate this, you can reintroduce context into each chunk. For instance, you
might want to repeat the blog post's title in every chunk. This is easily
achieved using the `formatting` parameter, which allows you to inject row data
into each chunk:

```sql
SELECT ai.create_vectorizer(   
    'blog'::regclass,
    destination => 'blog_contents_embeddings',
    embedding => ai.embedding_openai('text-embedding-3-small', 768),
    chunking => ai.chunking_character_text_splitter('contents'),
    formatting => ai.formatting_python_template('$title: $chunk'),
);
```

This approach ensures that each chunk retains important contextual information,
improving the quality and relevance of the embeddings.

### Querying the embedding

The `create_vectorizer` command generates a view with the same name as the
specified destination. This view contains all the embeddings for the blog table.
Note that you'll typically have multiple rows in the view for each blog entry,
as multiple embeddings are usually generated per source document.

The view includes all columns from the blog table, plus these additional columns:

| Column | Type | Description |
|--------|------|-------------|
| embedding_uuid | UUID | Unique identifier for the embedding |
| chunk | TEXT | The text segment that was embedded |
| embedding | VECTOR | The vector representation of the chunk |
| chunk_seq | INT | Sequence number of the chunk within the document, starting at 0 |

To find the closest embeddings to a query, use this canonical SQL query:

```sql
SELECT 
   chunk,
   embedding <=> <query embedding> as distance
FROM blog_contents_embeddings
ORDER BY distance 
LIMIT 10;
```

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

This approach works with any column from the blog table. For example, to search by author:

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

## Advanced vectorizer usage

### Formatting 

Formatting allows you to inject additional information into each chunk. This is
needed because splitting up the text into chunks can lead to a loss of important
context. For instance, you might want to include the authors and title with each
chunk. This is achieved using Python template strings, which have access to all
columns in the row and a special '$chunk' variable containing the chunk's text.

You may need to reduce the chunk size to ensure the formatted text fits within
token limits. Adjust the 'chunk_size' parameter of the text_splitter
accordingly:

```sql
SELECT ai.create_vectorizer(
    'blog'::regclass,
    destination => 'blog_contents_embeddings',
    embedding => ai.embedding_openai('text-embedding-3-small', 768),
    chunking => ai.chunking_character_text_splitter('contents', chunk_size => 700),
    formatting => ai.formatting_python_template('$title - by $author - $chunk'),
);
```

The default format string is simply '$chunk'.

### Indexing

The vectorizer can create a vector index on the embedding column to improve
query performance. By default, a vectorscale index is created after 100,000
rows, but you can specify other vector index types. Here's an example using an
HNSW index:

```sql
SELECT ai.create_vectorizer(
    'blog'::regclass,
    destination => 'blog_contents_embeddings',
    embedding => ai.embedding_openai('text-embedding-3-small', 768),
    chunking => ai.chunking_character_text_splitter('contents', chunk_size => 700),
    formatting => ai.formatting_python_template('$title - by $author - $chunk'),
    indexing => ai.indexing_hnsw(min_rows => 100000, opclass => 'vector_l2_ops')
);
```

Note: Indexing relies on a background job that runs periodically, so this
feature won't work if scheduling is disabled.

### Scheduling

By default, scheduling uses TimescaleDB background jobs running every five
minutes. You can disable this to run manually or through an external cron job:

```sql
SELECT ai.create_vectorizer(
    'blog'::regclass,
    destination => 'blog_contents_embeddings',
    embedding => ai.embedding_openai('text-embedding-3-small', 768),
    chunking => ai.chunking_character_text_splitter('contents', chunk_size => 700),
    formatting => ai.formatting_python_template('$title - by $author - $chunk'),
    scheduling => ai.scheduling_none(),
);
```

### Embedding storage table

The view is based on a table storing blog embeddings, named
`blog_contents_embeddings_store`. You can query this table directly for
potentially more efficient queries. The table structure is as follows:

```sql
CREATE TABLE blog_embedding_store(
    embedding_uuid UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),     
    id INT,  -- primary key referencing the blog table
    chunk_seq INT NOT NULL, 
    chunk TEXT NOT NULL,
    embedding VECTOR(768) NOT NULL,
    UNIQUE (id, chunk_seq),
    FOREIGN KEY (id) REFERENCES public.blog(id) ON DELETE CASCADE
);
```

## Monitoring the vectorizer

Since embeddings are created asynchronously, there may be a delay before they
become available. Use the `vectorizer_status` view to monitor the vectorizer's
status:

```sql
SELECT * FROM ai.vectorizer_status;
```

Sample output:

| id | source_table | target_table | view | pending_items |
|----|--------------|--------------|------|---------------|
| 1 | public.blog | public.blog_contents_embedding_store | public.blog_contents_embeddings | 1 |

The `pending_items` column indicates the number of items still awaiting embedding creation.