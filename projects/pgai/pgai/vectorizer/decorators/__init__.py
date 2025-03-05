"""
Vectorizer decorator module for pgai.

This module provides decorators for registering custom functions 
for each step of the vectorization process.
"""

from ..chunking import chunker, registered_chunkers
from ..embedding import embedding, registered_embeddings
from ..formatting import formatter, registered_formatters
from ..processing import processor, registered_processors

__all__ = [
    # Chunking
    "chunker",
    "registered_chunkers",
    
    # Embedding
    "embedding",
    "registered_embeddings",
    
    # Formatting
    "formatter", 
    "registered_formatters",
    
    # Processing
    "processor",
    "registered_processors",
]