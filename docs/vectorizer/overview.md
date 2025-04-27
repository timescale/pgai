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
[Vectorizer quick start](/docs/vectorizer/quick-start.md). For a more detailed technical specification, see the
[Vectorizer API reference](/docs/vectorizer/api-reference.md).

To make embedding generation performant, and resilient to intermittent LLM
endpoint failures, we use a background worker to perform the embedding
generation. When you create Vectorizers in a [Timescale Cloud](https://tsdb.co/gh-pgai-signup) database, the
worker runs automatically and creates and synchronizes the embeddings in the
background. When using a database on another cloud provider (AWS RDS, Supabase,
etc.) or self-hosted Postgres, you can use the [vectorizer worker](/docs/vectorizer/worker.md) to
process your vectorizers.

Let's explore how the Vectorizer can transform your approach to unstructured,
textual, data analysis, and semantic search:

- [Select an embedding provider and set up your API Keys](#select-an-embedding-provider-and-set-up-your-api-keys)
- [Define a vectorizer](#define-a-vectorizer)
- [Query an embedding](#query-an-embedding)
- [Inject context into vectorizer chunks](#inject-context-into-vectorizer-chunks)
- [Improve query performance on your Vectorizer](#improve-query-performance-on-your-vectorizer)
- [Control vectorizer run time](#control-the-vectorizer-run-time-)
- [The embedding storage table](#the-embedding-storage-table)
- [Monitor a vectorizer](#monitor-a-vectorizer)


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

The `loading` parameter specifies the source of the data to generate embeddings from. E.g. from the `contents` column.
Vectorizer supports other loaders, such as the
`ai.loading_uri`, which loads external documents from local or remote buckets like S3, etc.
For more details, check the [loading configuration](/docs/vectorizer/api-reference.md#loading-configuration) section 
of the vectorizer API reference.

Additionally, if the `contents` field is lengthy, it is split into multiple chunks,
resulting in several embeddings for a single blog post. Chunking helps
ensure that each embedding is semantically coherent, typically representing a
single thought or concept. A useful mental model is to think of embedding one
paragraph at a time.

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

On Timescale Cloud, vectorizers are created automatically and scheduled using TimescaleDB background jobs running
every five minutes. If you are self-hosting, you need to [run the vectorizer-worker](/docs/vectorizer/worker.md)
manually to create and run the vectorizer.

## Query an embedding

The `create_vectorizer` command generates a view with the same name as the
specified destination. This view contains all the embeddings for the blog table.
Note that you'll typically have multiple rows in the view for each blog entry,
as multiple embeddings are usually generated for each source document.

The view includes all columns from the blog table plus the following additional columns:

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

<details>
<summary>Click to see SQLAlchemy examples for querying the embeddings</summary>

Given an example SQLAlchemy model:

```python
    class Wiki(Base):
        __tablename__ = "wiki"
        
        id: Mapped[int] = mapped_column(primary_key=True)
        url: Mapped[str]
        title: Mapped[str]
        text: Mapped[str]

        # Add vector embeddings for the text field
        text_embeddings = vectorizer_relationship(
            target_table='wiki_embeddings',
            dimensions=384
        )
```

You can use the text_embeddings relationship to perform semantic search on the embeddings by ordering the results by distance.

```python
    async def _find_relevant_chunks(client: ollama.AsyncClient, query: str, limit: int = 2) -> WikiSearchResult:
        response = await client.embed(model="all-minilm", input=query)
        embedding = response.embeddings[0]
        with Session(engine) as session:
            # Query both the Wiki model and its embeddings
            result = session.query(
                Wiki,
                Wiki.text_embeddings.embedding.cosine_distance(embedding).label('distance')
            ).join(Wiki.text_embeddings).order_by(
                'distance'
            ).limit(limit).all()
            
        return result
```

You can, of course, add any other filters to the query.

</details>

## Inject context into vectorizer chunks

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

The view is based on a table storing blog embeddings, named
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

Vectorizer supports two different ways to store your embeddings:

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
    embedding => ai.embedding_openai('text-embedding-3-small', 768),
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
