from datetime import datetime, timezone

from typing_extensions import override
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship, Mapped
from pgvector.sqlalchemy import Vector # type: ignore

from db.engine import Base

from typing import Optional
from sqlalchemy.orm import mapped_column


# Defining the models for the database table


class CodeFile(Base):
    __tablename__ = "code_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=datetime.now(timezone.utc)
    )
    contents: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
    __table_args__ = {"info": {"is_view": True}}

    # Original CodeFile columns
    id: Mapped[int] = mapped_column(Integer, ForeignKey("code_files.id"), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    contents: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Embedding specific columns added by pgai
    embedding_uuid: Mapped[str] = mapped_column(String, primary_key=True)
    chunk: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)
    chunk_seq: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationship back to original CodeFile
    code_file: Mapped["CodeFile"] = relationship("CodeFile", foreign_keys=[id])

    @override
    def __repr__(self) -> str:
        return f"<CodeFileEmbedding(file_name='{self.file_name}', chunk_seq={self.chunk_seq})>"
