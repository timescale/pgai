"""
Example of a custom RAG pipeline using decorators.

This example demonstrates how to use the pgai vectorizer decorators 
to create a fully customized RAG pipeline.
"""

import asyncio
from typing import Any, Dict, List, Sequence

import openai
from pgai.vectorizer.decorators import (
    chunker,
    embedding,
    formatter,
    processor,
    registered_chunkers,
    registered_embeddings,
    registered_formatters,
    registered_processors,
)
from pgai.vectorizer.embeddings import ChunkEmbeddingError


@chunker(name="llm_based_chunker")
async def llm_based_chunker(item: dict[str, Any], config: dict[str, Any]) -> list[str]:
    """
    Custom chunking function that uses an LLM to intelligently chunk text.
    
    Args:
        item: The source document/row
        config: Configuration parameters
    
    Returns:
        A list of text chunks
    """
    text = item[config["text_column"]]
    if not text:
        return []
    
    # In a real implementation, you would call an LLM to determine logical breaking points
    # For this example, we'll use a simple approach
    prompt = f"""
    Please divide the following text into {config.get('max_chunks', 5)} logical chunks
    that preserve context and meaning. Return only the chunks, one per line:
    
    {text[:1000]}  # Truncated for the example
    """
    
    # Simulate LLM call
    # In real code: response = await call_llm_api(prompt, config)
    chunks = [
        "This is the first logical chunk of content...",
        "The second chunk continues with important details...",
        "Finally, the third chunk concludes the text...",
    ]
    
    return chunks


@formatter(name="llm_metadata_enricher")
async def llm_metadata_enricher(
    chunk: str, item: dict[str, Any], config: dict[str, Any]
) -> str:
    """
    Custom formatter that uses an LLM to enrich chunks with metadata.
    
    Args:
        chunk: The text chunk to format
        item: The source document/row
        config: Configuration parameters
    
    Returns:
        A formatted string with metadata
    """
    # In a real implementation, you would call an LLM to generate metadata
    # For simplicity, we'll simulate it here
    metadata_prompt = f"""
    Generate 3 relevant questions that could be answered by this text chunk:
    
    {chunk}
    """
    
    # Simulate LLM call
    # In real code: metadata = await call_llm_api(metadata_prompt, config)
    metadata = """
    Q1: What is the main topic of this text?
    Q2: What evidence supports the key argument?
    Q3: How does this relate to the broader context?
    """
    
    # Combine the original chunk with the generated metadata
    formatted_text = f"""
    # Original Content
    {chunk}
    
    # Metadata
    {metadata}
    """
    
    return formatted_text


@embedding(name="context_aware_embedding")
async def context_aware_embedding(
    documents: list[str], config: dict[str, Any]
) -> Sequence[list[float] | ChunkEmbeddingError]:
    """
    Custom embedding function that considers neighboring chunks for context.
    
    Args:
        documents: List of text documents to embed
        config: Configuration parameters
    
    Returns:
        A sequence of embedding vectors or errors
    """
    # This is just an example - in reality, you might want to use
    # a sliding window approach or other techniques to incorporate
    # context from neighboring chunks
    
    # For simplicity, we'll use OpenAI's embeddings API directly
    # but you could use any embedding model or approach
    
    client = openai.AsyncOpenAI(
        api_key=config["api_key"],
        base_url=config.get("base_url"),
    )
    
    results = []
    for doc in documents:
        try:
            # In a real implementation, you might preprocess the document
            # to incorporate context from neighboring chunks
            response = await client.embeddings.create(
                input=doc,
                model=config["model"],
                dimensions=config.get("dimensions", 1536),
            )
            results.append(response.data[0].embedding)
        except Exception as e:
            error = ChunkEmbeddingError(
                error="Embedding generation failed",
                error_details=str(e),
            )
            results.append(error)
    
    return results


# Example usage in a hypothetical application:

async def main():
    # Register custom functions with descriptive names
    print(f"Registered chunkers: {list(registered_chunkers.keys())}")
    print(f"Registered formatters: {list(registered_formatters.keys())}")
    print(f"Registered embeddings: {list(registered_embeddings.keys())}")
    print(f"Registered processors: {list(registered_processors.keys())}")
    
    # You could then create a vectorizer in SQL, and reference these custom functions
    # or build your own custom pipeline in Python


if __name__ == "__main__":
    asyncio.run(main())
    
# In SQL, you would create a vectorizer like:
"""
SELECT ai.create_vectorizer(
    source_table => 'documents',
    target_table => 'document_embeddings',
    chunking => '{"implementation": "llm_based_chunker", "text_column": "content", "max_chunks": 5}',
    formatting => '{"implementation": "llm_metadata_enricher"}',
    embedding => '{"implementation": "context_aware_embedding", "model": "text-embedding-3-small", "api_key_name": "OPENAI_API_KEY"}'
);
"""