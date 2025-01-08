"""Create documents vectorizer

Revision ID: 0002
Revises: 0001
Create Date: 2025-01-07 17:18:58.091881

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from pgai.alembic.configuration import OpenAIConfig, RecursiveCharacterTextSplitterConfig, \
    PythonTemplateConfig

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS ai CASCADE;")
    op.create_vectorizer(
        source_table="documents",
        embedding=OpenAIConfig(
            model='text-embedding-3-small',
            dimensions=768
        ),
        chunking=RecursiveCharacterTextSplitterConfig(
            chunk_column='content',
            chunk_size=800,
            chunk_overlap=200,
        ),
        formatting=PythonTemplateConfig(template='$file_name \n $chunk')
    )


def downgrade() -> None:
    op.drop_vectorizer(vectorizer_id=1, drop_all=True)
