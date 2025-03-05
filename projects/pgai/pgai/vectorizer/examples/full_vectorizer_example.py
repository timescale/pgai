"""
Example of a complete vectorizer function using the decorator pattern.

This example shows how a future version of pgai could support a full
vectorizer decorator that gives maximum flexibility.
"""

import asyncio
import numpy as np
from typing import Any, Tuple, List, Sequence

from pgai.vectorizer.embeddings import ChunkEmbeddingError


# This is a hypothetical vectorizer decorator that would handle the full pipeline
# Note: This is not implemented yet in pgai, but shows what could be possible
def vectorizer(name=None):
    """
    Hypothetical decorator for registering complete vectorizer functions.
    
    A vectorizer function takes a source row and returns embedding records and errors.
    """
    def decorator(func):
        # In a real implementation, this would register the function
        # in a global registry like the other decorators
        return func
    return decorator


@vectorizer(name="document_processing_pipeline")
async def process_document(
    item: dict[str, Any], 
    config: dict[str, Any]
) -> Tuple[List[List[Any]], List[Tuple[int, str, Any]]]:
    """
    A full vectorizer function that processes a document from start to finish.
    
    Args:
        item: Source row data
        config: Configuration
        
    Returns:
        Tuple of (embedding records, error records)
    """
    vectorizer_id = config.get("vectorizer_id", 1)
    primary_keys = config.get("primary_keys", ["id"])
    pk_values = [item[pk] for pk in primary_keys]
    
    # 1. Extract text from the document
    text = item.get(config.get("content_column", "content"), "")
    if not text:
        # Return early if no content
        error_record = (
            vectorizer_id,
            "Empty content",
            {"pk": {pk: val for pk, val in zip(primary_keys, pk_values)}},
        )
        return [], [error_record]
    
    # 2. Process the document to extract metadata
    # This could include OCR for images, parsing PDFs, etc.
    metadata = await extract_metadata(text, item, config)
    
    # 3. Chunk the document using custom logic
    chunks = await smart_chunking(text, metadata, config)
    
    # 4. Generate embeddings for each chunk
    embedding_records = []
    error_records = []
    
    for chunk_id, chunk in enumerate(chunks):
        # Format the chunk with metadata
        formatted_chunk = format_with_metadata(chunk, metadata, config)
        
        # Generate embedding
        try:
            embedding_vector = await generate_embedding(formatted_chunk, config)
            # Create embedding record: [pk1, pk2, ..., chunk_id, formatted_text, embedding]
            record = pk_values + [chunk_id, formatted_chunk, np.array(embedding_vector)]
            embedding_records.append(record)
        except Exception as e:
            # Create error record for failed embedding
            error = {
                "pk": {pk: val for pk, val in zip(primary_keys, pk_values)},
                "chunk_id": chunk_id,
                "chunk": formatted_chunk,
                "error_reason": str(e),
            }
            error_records.append((vectorizer_id, "Embedding failed", error))
    
    return embedding_records, error_records


# Helper functions for the pipeline

async def extract_metadata(text: str, item: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Extract metadata from the document using LLMs or other techniques."""
    # In a real implementation, this could use:
    # - LLM calls to extract entities, topics, etc.
    # - Computer vision for images
    # - Domain-specific extractors
    
    # Simple simulation
    metadata = {
        "title": item.get("title", "Untitled"),
        "summary": f"This is a summary of a document about {text.split()[:5]}...",
        "topics": ["topic1", "topic2"],
        "entities": ["entity1", "entity2"],
    }
    return metadata


async def smart_chunking(text: str, metadata: dict[str, Any], config: dict[str, Any]) -> list[str]:
    """Chunk the document using advanced techniques."""
    # Could implement:
    # - Semantic chunking with LLMs
    # - Sliding window with overlap
    # - Structure-aware chunking (paragraphs, sections)
    
    # Simple simulation
    chunks = []
    chunk_size = config.get("chunk_size", 1000)
    for i in range(0, len(text), chunk_size):
        chunks.append(text[i:i+chunk_size])
    return chunks


def format_with_metadata(chunk: str, metadata: dict[str, Any], config: dict[str, Any]) -> str:
    """Format a chunk with relevant metadata."""
    # Format chunk for optimal retrieval
    formatted = f"""
    TITLE: {metadata['title']}
    TOPICS: {', '.join(metadata['topics'])}
    
    CONTENT:
    {chunk}
    """
    return formatted


async def generate_embedding(text: str, config: dict[str, Any]) -> list[float]:
    """Generate an embedding vector for the text."""
    # In a real implementation, call embedding API
    # For simulation, return a random vector
    dimension = config.get("dimensions", 1536)
    return list(np.random.rand(dimension))


# Example usage
async def main():
    # Example source row
    document = {
        "id": 123,
        "title": "Understanding Artificial Intelligence",
        "content": "Artificial Intelligence (AI) is a field of computer science...",
        "created_at": "2025-02-04",
    }
    
    # Configuration
    config = {
        "vectorizer_id": 1,
        "primary_keys": ["id"],
        "content_column": "content",
        "dimensions": 1536,
        "model": "text-embedding-3-small",
    }
    
    # Process the document
    embedding_records, error_records = await process_document(document, config)
    
    # Print results
    print(f"Generated {len(embedding_records)} embedding records")
    print(f"Encountered {len(error_records)} errors")


if __name__ == "__main__":
    asyncio.run(main())