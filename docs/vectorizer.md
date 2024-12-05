# Automate AI embedding with pgai Vectorizer

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

- Designate any text column for embedding using customizable rules
- Automatically generate and maintain searchable embedding tables 
- Keep embeddings continuously synchronized with source data (asynchronously)
- Utilize a convenient view that seamlessly joins base tables with their embeddings

This page offers a comprehensive overview of Vectorizer features,
demonstrating how it streamlines the process of working with vector embeddings
in your database. To quickly try out embeddings using a pre-built Docker developer environment, see the 
[Vectorizer quick start](/docs/vectorizer-quick-start.md). For a more detailed technical specification, see the
[Vectorizer API reference](./vectorizer-api-reference.md).

Let's explore how the Vectorizer can transform your approach to unstructured,
textual, data analysis and semantic search:

- [Setup your API Keys](#setup-your-api-keys)
- [Define a vectorizer](#define-a-vectorizer)
- [Query an embedding](#query-an-embedding)
- [Inject context into vectorizer chunks](#inject-context-into-vectorizer-chunks)
- [Improve query performance on your Vectorizer](#improve-query-performance-on-your-vectorizer)
- [Control vectorizer run time](#control-the-vectorizer-run-time-)
- [The embedding storage table](#the-embedding-storage-table)
- [Monitor a vectorizer](#monitor-a-vectorizer)


## Setup your API Keys 

Before using Vectorizer, you need to setup your API keys for the embedding
service you are using. To store several API keys, you give each key a name and
reference them in the `embedding` section of the Vectorizer configuration. The default
API key names match the embedding provider's default name. For example, for OpenAI, the default 
key name is `OPENAI_API_KEY`.

Setting up your API keys is done differently depending on whether you are using Vectorizer in
Timescale Cloud or on a self-hosted Postgres server.

- Timescale Cloud

  1. In [Timescale Console > Project Settings](https://console.cloud.timescale.com/dashboard/settings), click `AI Model API Keys`.
  1. Click `Add AI Model API Keys`, add your key, then click `Add API key`.

  Your API key is stored securely in Timescale Cloud and not in your database.

- Self-hosted Postgres

  Set an environment variable that is the [same as your API key name](./vectorizer-worker.md#install-and-configure-vectorizer-worker). 
  For example:
  ```bash
  export OPENAI_API_KEY="Your OpenAI API key"
  ```

## Define a vectorizer

You can configure the system to automatically generate and update embeddings
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
    embedding => ai.embedding_ollama('nomic-embed-text', 768),
    chunking => ai.chunking_recursive_character_text_splitter('contents')
);
```

In this example, if the `contents` field is lengthy, it is split into multiple chunks, 
resulting in several embeddings for a single blog post. Chunking helps
ensure that each embedding is semantically coherent, typically representing a
single thought or concept. A useful mental model is to think of embedding one
paragraph at a time.

However, splitting text into chunks can sometimes lead to a loss of context. To
mitigate this, you can reintroduce context into each chunk. For instance, you
might want to repeat the blog post's title in every chunk. This is easily
achieved using the `formatting` parameter, which allows you to inject row data
into each chunk:

```sql
SELECT ai.create_vectorizer(   
    'blog'::regclass,
    destination => 'blog_contents_embeddings',
    embedding => ai.embedding_ollama('nomic-embed-text', 768),
    chunking => ai.chunking_recursive_character_text_splitter('contents'),
    formatting => ai.formatting_python_template('$title: $chunk')
);
```

This approach ensures that each chunk retains important contextual information,
improving the quality and relevance of the embeddings.

On Timescale Cloud, vectorizers are created automatically, and scheduled using TimescaleDB background jobs running
every five minutes. If you are self-hosting you need to [run the vectorizer-worker](./vectorizer-worker.md)
manually to create and run the vectorizer.

## Query an embedding

The `create_vectorizer` command generates a view with the same name as the
specified destination. This view contains all the embeddings for the blog table.
Note that you'll typically have multiple rows in the view for each blog entry,
as multiple embeddings are usually generated for each source document.

The view includes all columns from the blog table, plus the following additional columns:

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
   embedding <=> ai.ollama_embed('nomic-embed-text', <query>) as distance
FROM blog_contents_embeddings
ORDER BY distance
LIMIT 10;
```
The `ollama_embed` function generates an embedding for the provided string. The
`<=>` operator calculates the distance between the query embedding and each
row's embedding vector. This is a simple way to do semantic search.

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

## Inject context into vectorizer chunks

Formatting allows you to inject additional information into each chunk. This is
needed because splitting up the text into chunks can lead to a loss of important
context. For instance, you might want to include the authors and title with each
chunk. This is achieved using Python template strings, which have access to all
columns in the row and a special `$chunk` variable containing the chunk's text.

You may need to reduce the chunk size to ensure the formatted text fits within
token limits. Adjust the `chunk_size` parameter of the text_splitter
accordingly:

```sql
SELECT ai.create_vectorizer(
    'blog'::regclass,
    destination => 'blog_contents_embeddings',
    embedding => ai.embedding_ollama('nomic-embed-text', 768),
    chunking => ai.chunking_recursive_character_text_splitter('contents', chunk_size => 700),
    formatting => ai.formatting_python_template('$title - by $author - $chunk')
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
    destination => 'blog_contents_embeddings',
    embedding => ai.embedding_ollama('nomic-embed-text', 768),
    chunking => ai.chunking_recursive_character_text_splitter('contents', chunk_size => 700),
    formatting => ai.formatting_python_template('$title - by $author - $chunk'),
    indexing => ai.indexing_hnsw(min_rows => 100000, opclass => 'vector_l2_ops')
);
```

Note: Indexing relies on a background job that runs periodically, so this
feature will not work if scheduling is disabled (which is the default for self-hosted installations).

## Control the vectorizer run time 

When you use Vectorizer on Timescale Cloud, you use scheduling to control the time when vectorizers run.
A scheduled job checks if there is work to be done and, if so, runs the cloud function to embed the data.
By default, scheduling uses TimescaleDB background jobs running every five minutes.
Once the table is large enough, scheduling also handles index creation on the embedding column. 

When you self-host vectorizer, the vectorizer worker uses a polling mechanism to check whether
there is work to be done. Thus, scheduling is not needed, and is deactivated by default.

Note: when scheduling is disabled, the index is not created automatically. You need to create it manually.

## The embedding storage table

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

## Monitor a vectorizer

Since embeddings are created asynchronously, there may be a delay before they
become available. Use the `vectorizer_status` view to monitor the vectorizer's
status:

```sql
SELECT * FROM ai.vectorizer_status;
```

Sample output:

| id | source_table | target_table                         | view                            | pending_items |
|----|--------------|--------------------------------------|---------------------------------|---------------|
| 1  | public.blog  | public.blog_contents_embedding_store | public.blog_contents_embeddings | 1             |

The `pending_items` column indicates the number of items still awaiting embedding creation.
