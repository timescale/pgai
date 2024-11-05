from datetime import datetime, timezone
from typing_extensions import override
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from db.engine import Base


class CodeFile(Base):
    __tablename__ = "code_files"

    id = Column(Integer, primary_key=True)
    file_name = Column(String(255), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.now(timezone.utc))
    contents = Column(Text, nullable=True)

    @override
    def __repr__(self) -> str:
        return f"<CodeFile(file_name='{self.file_name}')>"


class CodeFileEmbedding(Base):
    """
    Model representing the view created by pgai vectorizer.
    This maps to the automatically created view 'code_files_embeddings'
    which joins the original code_files table with its embeddings.
    """

    __tablename__ = "code_files_embeddings"

    # We make this a view model by setting it as such
    __table_args__ = {"info": {"is_view": True}}

    # Original CodeFile columns
    id = Column(Integer, ForeignKey("code_files.id"), primary_key=True)
    file_name = Column(String(255), nullable=False)
    updated_at = Column(DateTime, nullable=True)
    contents = Column(Text, nullable=True)

    # Embedding specific columns added by pgai
    embedding_uuid = Column(String, primary_key=True)
    chunk = Column(Text, nullable=False)
    embedding = Column(
        Vector(768), nullable=False
    )  # 768 dimensions for text-embedding-3-small
    chunk_seq = Column(Integer, nullable=False)

    # Relationship back to original CodeFile
    code_file = relationship("CodeFile", foreign_keys=[id])

    @override
    def __repr__(self) -> str:
        return f"<CodeFileEmbedding(file_name='{self.file_name}', chunk_seq={self.chunk_seq})>"
