from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.config import settings
from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin, WorkspaceScopedMixin, get_utc_now
from app.models.vector import VectorType


class KnowledgeDocument(Base, UUIDMixin, TimestampMixin, WorkspaceScopedMixin):
    """A workspace-scoped knowledge source (uploaded file or pasted text).

    Lifecycle: pending -> processing -> indexed | failed
    """
    __tablename__ = "knowledge_documents"

    title = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=True)
    # 'upload' | 'text'
    source_type = Column(String(20), default="upload", nullable=False)
    content_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, default=0, nullable=False)
    char_count = Column(Integer, default=0, nullable=False)

    # Extracted plain text is retained so reindexing never depends on local disk.
    source_text = Column(Text, nullable=True)

    # 'pending' | 'processing' | 'indexed' | 'failed'
    status = Column(String(20), default="pending", nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    chunk_count = Column(Integer, default=0, nullable=False)

    embedding_provider = Column(String(50), nullable=True)
    embedding_model = Column(String(100), nullable=True)
    embedding_dimension = Column(Integer, nullable=True)

    uploaded_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    indexed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index.asc()",
    )
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_user_id])

    __table_args__ = (
        Index("ix_knowledge_documents_workspace_status", "workspace_id", "status"),
        Index("ix_knowledge_documents_workspace_updated", "workspace_id", "updated_at"),
    )


class DocumentChunk(Base, UUIDMixin, WorkspaceScopedMixin):
    """One embedded slice of a knowledge document; always workspace-scoped."""
    __tablename__ = "document_chunks"

    document_id = Column(
        String(36), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    char_count = Column(Integer, default=0, nullable=False)
    embedding = Column(VectorType(settings.EMBEDDING_DIMENSION), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    document = relationship("KnowledgeDocument", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
        Index("ix_document_chunks_workspace_document", "workspace_id", "document_id"),
    )
