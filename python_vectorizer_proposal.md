# pgai Python API Description

If you want to customize the vectorizer behaviour, you can use the pgai python library to define your own vectorizer implementations.
The pgai vectorizer follows this simple pipeline:

1. Chunk: Split the input text into chunks
2. Format: Format each chunk with additional context
3. Embed: Generate embeddings for each chunk

You can replace each of these steps with custom implementations or define a completely new custom vectorizer from scratch if the general pipeline doesn't fit your use case.

## Installation

```bash
pip install pgai
```

## Quick Start

### Implement a custom embedding function
```python
from pgai import Pgai
# Initialize the pgai application
pgai = Pgai()

@pgai.embedding("my_embedding")
def my_embedding(documents: list[str], config: dict[str, Any]) -> list[list[float]]:
    # Implementation
    return [[0.1, 0.2, 0.3] for _ in documents]

pgai.cli()
```

This example would allow you to configure the vectorizer with your custom embedding function as such:

```sql
ai.create_vectorizer(
    -- other config
    embedding => '{"implementation": "my_embedding"}'
);
```

You can follow the same pattern to define custom chunking and formatting functions.
The `pgai.cli()` function will start the vectorizer worker as usual.


### Implement a custom vectorizer

If you want to completely define a custom vectorizer from scratch, it works very similarly but notice that you have to define the full pipeline:

```python
@pgai.vectorizer("my_vectorizer")
def my_vectorizer(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[list[EmbeddingRecord | VectorizerErrorRecord]]:
    # Implementation
    return [
        [EmbeddingRecord(
            primary_key=row["id"],
            chunk_seq=0,
            chunk=row['content'],
            embedding=[0.1, 0.2, 0.3]
        )] for row in rows]

pgai.cli()
```

This would allow you to configure the vectorizer with your custom vectorizer function as such:

```sql
ai.create_vectorizer(
    -- other config
    vectorizer => '{"implementation": "my_vectorizer"}'
);
```

Note that this completely replaces the default vectorizer pipeline, so you have to implement the full pipeline in your custom vectorizer, and cannot use the existing chunking, formatting, and embedding functions.

If you want to use these in your custom vectorizer implementation, the functions are located in the `pgai.vectorizer` module and can be imported as such:

```python
from pgai.vectorizer.embedders import openai_embedding
from pgai.vectorizer.chunkers import recursive_text_splitter
from pgai.vectorizer.formatters import python_template_formatter
```

The configuration however will have to be passed explicitly to these functions, as they are not automatically resolved from the vectorizer configuration since you are overwriting that part.

## Advanced Usage
### Configuration Models

#### Embedding Configuration
It is possible and highly recommended to use Pydantic models for type-safe configuration. This is e.g. how our internal configuration models look like:

```python
class OpenAI(BaseModel):
    model: str
    dimensions: int | None = None
    user: str | None = None
    api_key: str | None = None
```

The embedding function is then defined as such:

```python
@pgai.embedding(name="openai", config_model=OpenAI)
def openai_embedding(documents: list[str], config: OpenAI) -> list[list[float]]:
    ...
```

The `api_key` field is a special field: if `api_key_name` is present in the configured embedding config the default vectorizer implementation will automatically fetch the API key from the database and inject it into the configuration or load the API key from the environment variable if it is not present in the database.

Other fields are validated directly from the database config to the config object. Note that if your database configuration does not match the Pydantic model, the vectorizer will fail to start.

With this configuration a user can define the vectorizer in SQL as such:

```sql
ai.create_vectorizer(
    -- other config
    embedding => '{"implementation": "openai", "model": "gpt-3", "dimensions": 768, "api_key_name": "OPENAI_API_KEY"}'
);
```
In fact this is exactly the json the `ai.embedding_openai` function will create.


#### Vectorizer Configuration
For the vectorizer configuration, we follow the same pattern. But it probably makes sense to work with nested pydantic models to structure the configuration. Here is an extremely simplified version of our internal configuration model:

```python
class RecursiveCharacterTextSplitterConfig(BaseModel):
    separators: list[str]
    
class PythonTemplateConfig(BaseModel):
    template: str

class OpenAIConfig(BaseModel):
    model: str

class VoyageAIConfig(BaseModel):
    model: str

class VectorizerConfig(BaseModel):
    chunking: RecursiveCharacterTextSplitterConfig
    formatting: PythonTemplateConfig
    embedding: OpenAIConfig | VoyageAIConfig
```

The vectorizer function is then defined as such:

```python
@pgai.vectorizer("default", config_model=VectorizerConfig)
def default_vectorizer(rows: list[dict[str, Any]], config: VectorizerConfig) -> list[list[EmbeddingRecord | VectorizerErrorRecord]]:
    ...
```

The user can then define the vectorizer in SQL as such:

```sql
ai.create_vectorizer(
    -- other config
    vectorizer => '{"chunking": {"separators": ["."]},' ||
                    '"formatting": {"template": "This is a chunk: $chunk"},' ||
                    ' "embedding": {"implementation": "openai", "model": "gpt-3"}}'
);
```

# Extended pgai Python API with Cloud Deployment Support

## Overview

The extended pgai Python API would maintain the same decorator-based approach for defining custom vectorizers, embeddings, chunkers, and formatters, but would add a deployment mechanism that allows users to push their custom implementations to Timescale Cloud without having to manage infrastructure themselves.

## Deployment Workflow

1. **Local Development**: Developers create and test their custom vectorizer implementations locally using the pgai Python API
2. **Deployment**: When ready, developers run `pgai vectorizer deploy` which packages and uploads their code to their Timescale Cloud database
3. **Cloud Execution**: Timescale Cloud automatically builds a container with the custom code and runs it to process vectorizers

## Project Structure

A typical project would look like this:

```
my-vectorizer-project/
├── vectorizer.py         # Main file with custom implementations
├── requirements.txt      # Python dependencies
└── additional_modules/   # Any additional Python modules needed
```

The `vectorizer.py` would be the entry point containing the Pgai instance and all custom implementations:

```python
from pgai import Pgai
import my_custom_module  # Local module

# Initialize pgai
pgai = Pgai()

@pgai.embedding("my_custom_embedding")
def my_custom_embedding(documents, config):
    # Custom implementation
    return [[0.1, 0.2, 0.3] for _ in documents]

# Register CLI command
pgai.cli()
```

## Deployment Command

The `pgai vectorizer deploy` command would:

1. Detect the `vectorizer.py` file in the current directory
2. Parse any custom implementations registered with the Pgai instance
3. Package the code, along with `requirements.txt`
4. Upload this package to the connected Timescale Cloud database
5. Trigger a build process in Timescale Cloud

Example usage:

```bash
# Connect to database once
pgai configure --db-url postgresql://user:pass@hostname:port/dbname

# Deploy the current project
pgai vectorizer deploy
```

## Database Storage

When deployed, the code would be stored in a dedicated system table in the database:

```sql
CREATE TABLE ai.vectorizer_custom_code (
    id SERIAL PRIMARY KEY,
    code_hash TEXT NOT NULL,
    code_bundle BYTEA NOT NULL,  -- ZIP file with code and requirements.txt
    requirements TEXT,           -- Contents of requirements.txt
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    deployed_at TIMESTAMP WITH TIME ZONE,
    status TEXT,                 -- e.g., 'pending', 'deployed', 'failed'
    error_message TEXT
);
```

A trigger on this table would notify Timescale Cloud to build a new container with the uploaded code.

## Container Build Process

When new code is uploaded, Timescale Cloud would:

1. Extract the code bundle
2. Create a Docker image with the required dependencies
3. Store it as the custom vectorizer container for this database
4. Update the status in the `ai.vectorizer_custom_code` table
5. And run it instead of our default vectorizer worker for this database


# From here on its fully AI generated and not accurate needs cleanup


## Full Decorator Registration System

### Embedding Decorator

```python
@pgai.embedding(config_model=VoyageAIConfig)
async def voyage_embedding(
    documents: List[str], 
    config: VoyageAIConfig
) -> Sequence[Union[List[float], ChunkEmbeddingError]]:
    """
    Create embeddings using VoyageAI API.
    
    Args:
        documents: List of text documents to embed
        config: Configuration for the VoyageAI embedder
        
    Returns:
        List of embedding vectors or errors
    """
    # Implementation
    return await VoyageAI(**config.dict()).embed(documents)
```

### Chunking Decorator

```python
@pgai.chunking(config_model=RecursiveCharacterTextSplitterConfig)
def recursive_character_text_splitter(
    row: SourceRow,
    config: RecursiveCharacterTextSplitterConfig
) -> List[str]:
    """
    Split text into chunks using recursive character splitting.
    
    Args:
        row: Source row from database
        config: Configuration for the chunker
        
    Returns:
        List of text chunks
    """
    text = row[config.chunk_column]
    # Implementation using LangChain's text splitter
    return chunker.split_text(text)
```

### Formatting Decorator

```python
@pgai.formatting(config_model=PythonTemplateConfig)
def python_template_formatter(
    row: SourceRow,
    chunk: str,
    config: PythonTemplateConfig
) -> str:
    """
    Format a chunk with context from the source row.
    
    Args:
        row: Source row from database
        chunk: Text chunk to format
        config: Configuration for the formatter
        
    Returns:
        Formatted chunk
    """
    template = string.Template(config.template)
    context = {k: v for k, v in row.items()}
    context["chunk"] = chunk
    return template.safe_substitute(context)
```

## Vectorizer Decorator

```python
@pgai.vectorizer("default")
async def default_vectorizer(
    rows: List[SourceRow], 
    config: VectorizerConfig
) -> List[List[Union[EmbeddingRow, EmbeddingError]]]:
    """
    Default vectorizer that follows parse -> chunk -> format -> embed pipeline.
    
    Args:
        rows: List of source rows from database
        config: Configuration for the vectorizer
        
    Returns:
        List of embedding rows or errors for each source row
    """
    # Resolve components from config
    chunker = pgai.get_chunker(config.chunking_name)
    formatter = pgai.get_formatter(config.formatting_name)
    embedder = pgai.get_embedder(config.embedding_name)
    
    results = []
    for row in rows:
        # Process each row
        try:
            # 1. Chunk the source row
            chunks = chunker(row, config.chunking_config)
            
            # 2. Format each chunk
            formatted_chunks = [formatter(row, chunk, config.formatting_config) for chunk in chunks]
            
            # 3. Generate embeddings
            embeddings = await embedder(formatted_chunks, config.embedding_config)
            
            # 4. Create embedding rows
            row_results = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                if isinstance(embedding, ChunkEmbeddingError):
                    row_results.append(EmbeddingError(
                        source_id=row["id"],
                        error=str(embedding)
                    ))
                else:
                    row_results.append(EmbeddingRow(
                        source_id=row["id"],
                        chunk_seq=i,
                        chunk=chunk,
                        embedding=embedding
                    ))
            results.append(row_results)
        except Exception as e:
            results.append([EmbeddingError(
                source_id=row["id"],
                error=str(e)
            )])
    
    return results
```

## Custom Vectorizer Example

```python
@pgai.vectorizer("llm_enhanced_vectorizer")
async def llm_enhanced_vectorizer(
    rows: List[SourceRow],
    config: Dict[str, Any]
) -> List[List[Union[EmbeddingRow, EmbeddingError]]]:
    """
    A custom vectorizer that enhances chunks with LLM-generated metadata.
    
    Args:
        rows: List of source rows from database
        config: Custom configuration
        
    Returns:
        List of embedding rows or errors for each source row
    """
    results = []
    
    # Get the base embedding model
    embedding_model = pgai.get_embedder("voyage_embedding")
    
    for row in rows:
        try:
            # Custom chunking logic
            text = row["content"]
            chunks = custom_chunk_function(text)
            
            # Generate metadata for each chunk using an LLM
            enhanced_chunks = []
            for chunk in chunks:
                # Call an LLM to generate potential questions this chunk could answer
                metadata = await call_llm_for_metadata(chunk)
                # Combine original chunk with metadata
                enhanced_chunk = f"Questions this answers: {metadata}\n\nContent: {chunk}"
                enhanced_chunks.append(enhanced_chunk)
            
            # Generate embeddings for enhanced chunks
            embeddings = await embedding_model(enhanced_chunks, config["embedding_config"])
            
            # Create embedding rows
            row_results = []
            for i, (original_chunk, enhanced_chunk, embedding) in enumerate(zip(chunks, enhanced_chunks, embeddings)):
                if isinstance(embedding, ChunkEmbeddingError):
                    row_results.append(EmbeddingError(
                        source_id=row["id"],
                        error=str(embedding)
                    ))
                else:
                    row_results.append(EmbeddingRow(
                        source_id=row["id"],
                        chunk_seq=i,
                        chunk=original_chunk,  # Store original chunk
                        metadata={"enhanced_text": enhanced_chunk},  # Store enhanced version in metadata
                        embedding=embedding
                    ))
            results.append(row_results)
        except Exception as e:
            results.append([EmbeddingError(
                source_id=row["id"],
                error=str(e)
            )])
    
    return results
```

## Image/Document Support Example

```python
@pgai.vectorizer("document_vectorizer")
async def document_vectorizer(
    rows: List[SourceRow],
    config: Dict[str, Any]
) -> List[List[Union[EmbeddingRow, EmbeddingError]]]:
    """
    A vectorizer that handles document files from the database.
    
    Args:
        rows: List of source rows from database
        config: Configuration for document processing
        
    Returns:
        List of embedding rows or errors for each source row
    """
    results = []
    
    for row in rows:
        try:
            # Assume file content is stored in a bytea column
            file_content = row["file_content"]
            file_type = row["file_type"]
            
            # Process file based on type
            if file_type.startswith("image/"):
                # Process image
                text = await process_image_with_vision_model(file_content)
            elif file_type == "application/pdf":
                # Process PDF
                text = extract_text_from_pdf(file_content)
            elif file_type.startswith("text/"):
                # Process text file
                text = file_content.decode("utf-8")
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
            
            # Continue with regular chunking and embedding
            chunks = text_splitter.split_text(text)
            embeddings = await embedder(chunks, config["embedding_config"])
            
            # Create embedding rows
            row_results = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                if isinstance(embedding, ChunkEmbeddingError):
                    row_results.append(EmbeddingError(
                        source_id=row["id"],
                        error=str(embedding)
                    ))
                else:
                    row_results.append(EmbeddingRow(
                        source_id=row["id"],
                        chunk_seq=i,
                        chunk=chunk,
                        embedding=embedding
                    ))
            results.append(row_results)
        except Exception as e:
            results.append([EmbeddingError(
                source_id=row["id"],
                error=str(e)
            )])
    
    return results
```

## Running the Vectorizer Worker

```python
# Start the vectorizer worker with specific vectorizers
pgai.run(vectorizers=["default", "llm_enhanced_vectorizer"])

# Or run all registered vectorizers
pgai.run()

# Or run specific vectorizer with configuration
pgai.run_vectorizer("llm_enhanced_vectorizer", 
                    config={"embedding_config": {"model": "voyage-3-lite", "dimensions": 768}})
```

## Integration with SQL Configuration

```python
# Initialize with database connection
pgai = Pgai(db_url="postgres://postgres:password@localhost:5432/mydb")

# Register components that will be available to SQL-defined vectorizers
@pgai.embedding(name="openai", config_model=OpenAIEmbeddingConfig)
async def openai_embedding(documents, config):
    # implementation

@pgai.chunking(name="recursive_text_splitter", config_model=RecursiveCharacterTextSplitterConfig)
def recursive_text_splitter(row, config):
    # implementation

# Run the worker that will process vectorizers defined in SQL
pgai.run()
```

When a user defines a vectorizer in SQL using `ai.create_vectorizer()`, the worker will:
1. Read the configuration from the database
2. Map the configuration to the registered components
3. Execute the appropriate functions with the parsed configuration

## Error Handling and Monitoring

```python
# Register error handlers
@pgai.on_error
def log_error(error: Exception, context: Dict[str, Any]):
    """Log errors that occur during vectorization"""
    logger.error(f"Error in vectorizer {context['vectorizer_name']}: {error}")
    
# Register metrics collectors
@pgai.on_metrics
def collect_metrics(metrics: Dict[str, Any]):
    """Collect metrics about vectorizer operations"""
    prometheus_client.gauge('pgai_vectorizer_processed_rows', 
                           metrics['processed_rows'],
                           ['vectorizer_name'])
```

## Advanced: Using Framework Integration

```python
# Example integrating with FastAPI
from fastapi import FastAPI

app = FastAPI()

# Create pgai instance
pgai = Pgai(db_url="postgres://postgres:password@localhost:5432/mydb")

# Register vectorizers
@pgai.vectorizer("api_vectorizer")
async def api_vectorizer(rows, config):
    # implementation

# Register event handlers to start/stop pgai with the FastAPI app
@app.on_event("startup")
async def startup_event():
    # Start pgai worker in background
    asyncio.create_task(pgai.run())

@app.on_event("shutdown")
async def shutdown_event():
    # Stop pgai worker
    await pgai.stop()

# FastAPI routes
@app.get("/vectorizers")
async def get_vectorizers():
    return {"vectorizers": pgai.list_vectorizers()}
```

## Integration with Unit Testing

```python
# Example unit test for a custom vectorizer
import unittest
from unittest.mock import patch, MagicMock

class TestCustomVectorizer(unittest.TestCase):
    def setUp(self):
        self.pgai = Pgai(db_url="sqlite:///:memory:")
        
        # Register the vectorizer to test
        @self.pgai.vectorizer("test_vectorizer")
        async def test_vectorizer(rows, config):
            # Implementation
            return [[EmbeddingRow(source_id=row["id"], chunk_seq=0, chunk="test", embedding=[0.1, 0.2, 0.3])] 
                   for row in rows]
    
    @patch('pgai.embedding_models.voyage.VoyageAI')
    async def test_vectorizer_processing(self, mock_voyage):
        # Mock the embedding model
        mock_instance = MagicMock()
        mock_instance.embed.return_value = [[0.1, 0.2, 0.3]]
        mock_voyage.return_value = mock_instance
        
        # Create test data
        test_rows = [{"id": 1, "content": "Test content"}]
        
        # Get the vectorizer
        vectorizer = self.pgai.get_vectorizer("test_vectorizer")
        
        # Execute the vectorizer
        results = await vectorizer(test_rows, {})
        
        # Assertions
        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]), 1)
        self.assertEqual(results[0][0].source_id, 1)
        self.assertEqual(results[0][0].chunk, "test")
        self.assertEqual(results[0][0].embedding, [0.1, 0.2, 0.3])
```

This API design provides a flexible, type-safe way to define custom vectorization pipelines while maintaining backward compatibility with SQL-defined vectorizers. The decorator-based approach makes it easy to register components and compose them into complete pipelines.

What do you think of this approach? Any specific areas you'd like me to expand on or refine?