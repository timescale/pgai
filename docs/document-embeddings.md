# Document Loading and Parsing with pgai

pgai provides built-in functionality to automatically load, parse, and embed documents from external sources like URLs or file paths. This enables you to create embeddings from documents stored outside your database with minimal configuration.

## Overview

The document loading system works with the concept of a loader that you have to configure.
The loader is responsible for loading documents from external sources if provided a URL or file path.

## Basic Usage

Here's a simple example of creating a vectorizer that loads documents from URLs:

```sql
SELECT ai.create_vectorizer
( 'public.wiki'::regclass
, loader => ai.loader_from_document(file_uri_column => 'url')
, embedding => ai.embedding_openai('text-embedding-3-small', 1536)
, chunking => ai.chunking_recursive_character_text_splitter()
);
```

This configuration will:
1. Look for URLs in the specified column ('url')
2. Download and parse the documents 
3. Convert them to markdown text
4. Create embeddings using the OpenAI API

## Document Loaders

### ai.loader_from_document()

Creates a loader configuration for the vectorizer.

Parameters:
- `file_uri_column` (text, required): Name of the column containing URLs or file paths

Example with S3:
```sql
SELECT ai.create_vectorizer
( 'public.documents'::regclass
, loader => ai.loader_from_document(file_uri_column => 'document_url')
, embedding => ai.embedding_openai('text-embedding-3-small', 1536)
, chunking => ai.chunking_recursive_character_text_splitter()
);
```

## Document Parsers

### ai.parser_auto()

The default parser that automatically detects file types and uses appropriate parsing strategies.

Currently supported file types:
- PDF (.pdf)
- Text (.txt)
- Ebooks (.epub and .mobi)
- Images (.jpg, .png)

Example with explicit parser:
```sql
SELECT ai.create_vectorizer
( 'public.documents'::regclass
, loader => ai.loader_from_document(file_uri_column => 'url')
, parser => ai.parser_auto()
, embedding => ai.embedding_openai('text-embedding-3-small', 1536)
, chunking => ai.chunking_recursive_character_text_splitter()
);
```

## Storage Options

The document loading system supports both local file system and Amazon S3 storage using the [smart-open](https://pypi.org/project/smart-open/) library under the hood.

### Local Storage

For local file system storage, use local file paths in your URI column:

```sql
-- Create a table with local file paths
CREATE TABLE documents (
    id INT PRIMARY KEY,
    file_path TEXT NOT NULL
);

-- Insert documents with local paths
INSERT INTO documents (id, file_path) VALUES 
(1, '/path/to/documents/report.pdf'),
(2, '/path/to/documents/manual.pdf');

-- Create vectorizer for local files
SELECT ai.create_vectorizer(
    'public.documents'::regclass,
    loader => ai.loader_from_document(
        file_uri_column => 'file_path'
    ),
    embedding => ai.embedding_openai('text-embedding-3-small', 1536),
    chunking => ai.chunking_recursive_character_text_splitter()
);
```

### S3 Storage
For Amazon S3 storage, use s3:// URLs in your URI column. The vectorizer worker uses AWS credentials from standard AWS configuration sources:

Environment variables (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY)
AWS credentials file (~/.aws/credentials)
IAM roles when running on AWS infrastructure

Example usage:
```sql
-- Create a table with S3 URLs
CREATE TABLE documents (
    id INT PRIMARY KEY,
    s3_url TEXT NOT NULL
);
    
-- Insert documents with S3 paths
INSERT INTO documents (id, s3_url) VALUES 
(1, 's3://my-bucket/documents/report.pdf'),
(2, 's3://my-bucket/documents/manual.pdf');

-- Create vectorizer for S3 files
SELECT ai.create_vectorizer(
    'public.documents'::regclass,
    loader => ai.loader_from_document(file_uri_column => 's3_url'),
    embedding => ai.embedding_openai('text-embedding-3-small', 1536),
    chunking => ai.chunking_recursive_character_text_splitter()
);
```
If you're using environment variables for AWS credentials:
```bash
# Set AWS credentials before running the vectorizer worker
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```
The vectorizer worker will automatically handle downloading files from S3, parsing them, and generating embeddings.

## Integration with Chunking

The document loader integrates with pgai's chunking system.
When no chunk_column is specified in the chunking configuration, the loader's parsed markdown text is used as input:

```sql
SELECT ai.create_vectorizer
( 'public.documents'::regclass
, loader => ai.loader_from_document(file_uri_column => 'url')
, chunking => ai.chunking_recursive_character_text_splitter()  -- Uses parsed document text
, embedding => ai.embedding_openai('text-embedding-3-small', 1536)
);
```