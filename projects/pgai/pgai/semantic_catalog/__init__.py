"""Semantic Catalog for PostgreSQL databases.

This package provides functionality for creating and managing semantic catalogs
that store metadata about database objects along with natural language descriptions
and vector embeddings. The semantic catalog enables:

- Document database schemas with AI-generated natural language descriptions
- Search database objects using natural language queries
- Generate SQL statements based on natural language prompts
- Manage database documentation

Main components include:
- SemanticCatalog: Main class for interacting with a semantic catalog
- Management functions: create, from_id, from_name, list_semantic_catalogs
- Vectorization: Create embeddings for database objects to enable semantic search
- SQL generation: Generate SQL statements based on natural language queries
"""

from .semantic_catalog import (
    CatalogConnection,
    SemanticCatalog,
    TargetConnection,
    create,
    from_id,
    from_name,
    list_semantic_catalogs,
)

__all__ = [
    "list_semantic_catalogs",
    "from_name",
    "from_id",
    "create",
    "SemanticCatalog",
    "TargetConnection",
    "CatalogConnection",
]
