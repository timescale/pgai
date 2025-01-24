"""Change vectorizer configuration

Revision ID: 0003
Revises: 0002
Create Date: 2025-01-24 11:47:39.340279

"""

from collections.abc import Sequence

from alembic import op
from pgai.vectorizer.configuration import (
    ChunkingRecursiveCharacterTextSplitterConfig,
    EmbeddingOpenaiConfig,
    FormattingPythonTemplateConfig,
)

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_vectorizer("documents_embedding_store", drop_all=True)
    op.execute("TRUNCATE TABLE documents")
    op.create_vectorizer(
        source="documents",
        embedding=EmbeddingOpenaiConfig(model="text-embedding-3-small", dimensions=768),
        chunking=ChunkingRecursiveCharacterTextSplitterConfig(
            chunk_column="content",
            chunk_size=2000,
            chunk_overlap=200,
            separators=["\n## ", "\n# ", "\n", " ", ""],
        ),
        formatting=FormattingPythonTemplateConfig(template="$file_name \n $chunk"),
    )


def downgrade() -> None:
    op.drop_vectorizer("documents_embedding_store", drop_all=True)
