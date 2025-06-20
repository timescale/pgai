"""Create documents vectorizer

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-07 17:18:58.091881

"""

from collections.abc import Sequence

from alembic import op
from pgai.vectorizer.configuration import (
    ChunkingRecursiveCharacterTextSplitterConfig,
    EmbeddingOpenaiConfig,
    FormattingPythonTemplateConfig,
)

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS ai VERSION '0.8.0' CASCADE;")
    op.create_vectorizer(
        source="documents",
        embedding=EmbeddingOpenaiConfig(model="text-embedding-3-small", dimensions=768),
        chunking=ChunkingRecursiveCharacterTextSplitterConfig(
            chunk_column="content",
            chunk_size=800,
            chunk_overlap=200,
        ),
        formatting=FormattingPythonTemplateConfig(template="$file_name \n $chunk"),
    )


def downgrade() -> None:
    op.drop_vectorizer("documents_embedding_store", drop_all=True)
