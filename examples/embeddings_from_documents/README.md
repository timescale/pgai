# Tutorial: Generating document embeddings with PGAI

This tutorial will guide you through the process of generating embeddings for documents using the PGAI extension for PostgreSQL.

## Prerequisites

- Download this example subdirectory. You can quickly do it by generating a downloadable `.zip` file from [here](https://download-directory.github.io/?url=https%3A%2F%2Fgithub.com%2Ftimescale%2Fpgai%2Ftree%2Fmain%2Fexamples%2Fembeddings_from_documents).
- PostgreSQL database with the PGAI extension installed. Refer to [pgai install](/docs/README.md#pgai-install) for installation instructions.
- Documents to process (supports various formats including MD, XLSX, HTML, PDF). We will use those available in the [documents](documents) directory.
- A running instance of the [Vectorizer Worker](/docs/vectorizer/worker.md). In order to load the documents from the [documents](documents) directory, you need to modify the `compose-dev.yaml` file found [here](/projects/pgai/compose-dev.yaml), and add the following volume to the `vectorizer-worker` service:
   ```yaml
   volumes:
      - ./documents:/app/documents
   ```

## Step 1: Create the documents table

First, create a table to store the metadata of your documents:

```sql
CREATE TABLE documentation (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    file_uri TEXT NOT NULL
);
```

- `id`: Unique identifier for each document
- `title`: Document title
- `file_uri`: URI of the document file. Refer to the [ai.loading_uri function documentation](/docs/vectorizer/api-reference.md#ailoading_uri) for supported URIs.

## Step 2: Populate the table

Add your documents to the table. PGAI supports both local files and remote storage (like S3):

```sql
INSERT INTO documentation (title, file_uri) VALUES
('pgai documentation', '/app/documents/pgai.md'),                               -- Markdown README from PGAI repository
('pgai models support table', '/app/documents/pgai_models_support.xlsx'),       -- Excel file with model capabilities
('pgvectorscale documentation', '/app/documents/pgvectorscale.html'),           -- HTML documentation
('Sacred Texts of Postgres', '/app/documents/sacred_texts_of_postgres.pdf');    -- A PDF short book
```

> [!TIP]
> Feel free to add any other document. Additionally, you can load documents from remote storages such as Amazon S3. See [ai.loading_uri](/docs/vectorizer/api-reference.md#ailoading_uri) for more details.

## Step 3: Configure and create the vectorizer

The vectorizer configuration consists of several components. Four are the ones we are interested in this case:

1. **Loading**: Specifies how to load data. In our case, documents. Refer to the [ai.loading_uri function](/docs/vectorizer/api-reference.md#ailoading_uri) for more details. 
2. **Parsing**: Determines the data format conversion. Refer to the [ai.parsing_auto function](/docs/vectorizer/api-reference.md#aiparsing_auto) for more details.
3. **Chunking**: Defines text splitting strategy. Refer to the [ai.chunking_recursive_character_text_splitter function](/docs/vectorizer/api-reference.md#aichunking_recursive_character_text_splitter) for more details.
4. **Embedding**: Configures the embedding model. Refer to the [ai.embedding_openai function](/docs/vectorizer/api-reference.md#aiembedding_openai) for more details or [explore other available models](/docs/README.md#pgai-model-calling).

```sql
SELECT ai.create_vectorizer(
    'documentation'::regclass,
    loading => ai.loading_uri(column_name => 'file_uri'),
    parsing => ai.parsing_auto(),
    chunking => ai.chunking_recursive_character_text_splitter(
        chunk_size => 700,
        separators => array[E'\n\n', E'\n', '.', '?', '!', ' ', '', '|']
    ),
    embedding => ai.embedding_openai('text-embedding-3-small', 768)     
);
```

## Step 4: Monitor the vectorization progress

The vectorizer worker processes documents in the background. Monitor progress with:

```sql
SELECT * FROM ai.vectorizer_status;
```

When there are no pending items, the embedding generation is complete.

## Step 5: Query embeddings

Once vectorization is complete, you can perform any operation on top of those vectors. Here are some example queries with semantic similarity searches:

```sql
-- Search for content about the postgres ai extension
SELECT title,
       file_uri,
       embedding <=> ai.openai_embed('text-embedding-3-small', 'postgres ai extension', dimensions=>768) AS distance
FROM documentation_embedding
ORDER BY distance
LIMIT 2;

-- Search for content about Cohere chat capabilities support in pgai
SELECT title,
       file_uri,
       embedding <=> ai.openai_embed('text-embedding-3-small', 'Cohere chat complete', dimensions=>768) AS distance
FROM documentation_embedding
ORDER BY distance
LIMIT 2;

-- Search for content about pgvectorscale
SELECT title,
       file_path,
       embedding <=> ai.openai_embed('text-embedding-3-small', 'Statistical Binary Quantization', dimensions=>768) AS distance
FROM documentation_embedding
ORDER BY distance limit 2;

-- Search for specific content in the PDF book
SELECT title,
       file_uri,
       embedding <=> ai.openai_embed('text-embedding-3-small', 'blessed postgres', dimensions=>768) AS distance
FROM documentation_embedding
ORDER BY distance
LIMIT 2;
```

### Understanding the query results:
- Queries return the most semantically similar documents.
- Lower distance values indicate closer matches.
- Results include both documents stored locally and remotely (if any).
- Read [pgvector documentation](https://github.com/pgvector/pgvector) for more details on vector similarity search functions.

## Automatic synchronization

PGAI automatically handles updates, inserts and deletes to the source table(`documentation` in this example): 
- When you modify the source table content, embeddings are regenerated. For example, if the `file_uri` column is updated, the corresponding document embedding is automatically updated.
- No manual intervention needed to keep embeddings in sync.

## Troubleshooting

1. **File Access**: 
   - Verify PostgreSQL has read permissions for the document files.
   - Ensure file paths are correct and accessible.
   - When using a remote file storage, check you configured the correct credentials. See [/docs](/docs/vectorizer/api-reference.md#ailoading_uri) for more details about how to configure your credentials.

2. **Parser Selection**:
   - If auto-parsing fails, try specific parsers.
   - Verify [file formats compatibility](/docs/vectorizer/api-reference.md#ailoading_uri).

## Next steps and ideas

- Experiment with different parsing strategies.
- Try various embedding models.
- Try different chunking methods and add custom metadata for enhanced search.
- Explore advanced similarity search techniques.