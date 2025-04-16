from pathlib import Path

import psycopg

import pgai
from pgai.vectorizer.generate.config_generator import (
    generate_config_classes,
    generate_vectorizer_params,
)
from pgai.vectorizer.generate.function_parser import (
    get_function_metadata,
    read_create_vectorizer_metadata,
)

VECTORIZER_FUNCTIONS = [
    "loading_column",
    "loading_uri",
    "parsing_auto",
    "parsing_none",
    "parsing_pymupdf",
    "parsing_docling",
    "embedding_litellm",
    "embedding_openai",
    "embedding_ollama",
    "embedding_voyageai",
    "embedding_litellm",
    "chunking_character_text_splitter",
    "chunking_recursive_character_text_splitter",
    "chunking_none",
    "formatting_python_template",
    "indexing_diskann",
    "indexing_hnsw",
    "indexing_default",
    "indexing_none",
    "scheduling_default",
    "scheduling_none",
    "scheduling_timescaledb",
    "processing_default",
    "destination_table",
    "destination_column",
]


def list_vectorizer_functions(conn: psycopg.Connection) -> list[str]:
    """List all available vectorizer functions in the database."""
    query = """
    SELECT p.proname
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'ai'
      AND p.proname = ANY(%s)
    ORDER BY p.proname
    """

    with conn.cursor() as cur:
        cur.execute(query, (VECTORIZER_FUNCTIONS,))
        return [row[0] for row in cur]


def generate_vectorizer_configs(
    conn_str: str, output_file: Path, vectorizer_output_file: Path
) -> None:
    """Generate all vectorizer configuration classes."""
    pgai.install(conn_str)
    with psycopg.connect(conn_str) as conn:
        available_functions = list_vectorizer_functions(conn)
        functions = get_function_metadata(conn, available_functions)
        generate_config_classes(functions, output_file)
        vectorizer_params = read_create_vectorizer_metadata(conn)
        generate_vectorizer_params(vectorizer_params, vectorizer_output_file, functions)


def generate_models():
    # Connect to database
    conn_str = "postgresql://postgres:postgres@localhost:5432/postgres"
    output_file = Path("../../vectorizer/configuration.py")
    vectorizer_output_file = Path("../../vectorizer/create_vectorizer.py")
    generate_vectorizer_configs(conn_str, output_file, vectorizer_output_file)


if __name__ == "__main__":
    generate_models()
