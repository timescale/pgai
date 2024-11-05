"""Add embeddings to table

Revision ID: bb79790304f7
Revises: 497e69a2bca9
Create Date: 2024-11-04 11:48:35.807278

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "bb79790304f7"
down_revision: Union[str, None] = "497e69a2bca9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable required extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector CASCADE;")
    op.execute("CREATE EXTENSION IF NOT EXISTS ai CASCADE;")

    # Create the vectorizer
    op.execute("""
    SELECT ai.create_vectorizer(
        'code_files'::regclass,
        destination => 'code_files_embeddings',
        embedding => ai.embedding_openai('text-embedding-3-small', 768),
        chunking => ai.chunking_recursive_character_text_splitter(
            'contents',
            chunk_size => 1000,
            chunk_overlap => 200
        ),
        formatting => ai.formatting_python_template(
            'File: $file_name\n\nContents:\n$chunk'
        )
    );
    """)


def downgrade() -> None:
    # Drop the vectorizer
    op.execute("""
    SELECT ai.drop_vectorizer(
        (SELECT id FROM ai.vectorizer WHERE target_table = 'code_files_embeddings_store')
    );
    """)

    # Drop the created views and tables
    op.execute("DROP VIEW IF EXISTS code_files_embeddings;")
    op.execute("DROP TABLE IF EXISTS code_files_embeddings_store;")
