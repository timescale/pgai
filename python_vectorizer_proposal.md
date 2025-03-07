# pgai Python API Description

## Core Components

```python
from pgai import Pgai, SourceRow, EmbeddingRow, EmbeddingError, ChunkEmbeddingError
from typing import List, Dict, Any, Sequence, Union, Callable, Awaitable, Optional, TypeVar, Generic
from pydantic import BaseModel
import asyncio

# Initialize the pgai application
pgai = Pgai(
    db_url="postgres://postgres:postgres@localhost:5432/postgres",
    poll_interval="5s",
    concurrency=3
)
```

## Configuration Models

Pydantic models for type-safe configuration:

```python
class VoyageAIConfig(BaseModel):
    model: str
    dimensions: int
    api_key_name: str = "VOYAGE_API_KEY"
    input_type: Optional[str] = "document"


class RecursiveCharacterTextSplitterConfig(BaseModel):
    chunk_column: str
    chunk_size: int = 800
    chunk_overlap: int = 400
    separators: List[str] = ["\n\n", "\n", ".", "?", "!", " ", ""]
    is_separator_regex: bool = False


class PythonTemplateConfig(BaseModel):
    template: str = "$chunk"

class VectorizerConfig(BaseModel):
    """Configuration for a vectorizer"""
    name: str
    source_table: str
    destination: Optional[str] = None
    batch_size: int = 100
```

## Decorator Registration System

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