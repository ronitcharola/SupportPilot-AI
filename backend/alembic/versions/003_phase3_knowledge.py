"""Phase 3 migration: knowledge_documents and document_chunks

PostgreSQL gets a real pgvector embedding column plus an HNSW cosine index.
SQLite stores the same embeddings as JSON text and scores them in Python.

Revision ID: 003_phase3_knowledge
Revises: 002_phase2_tickets
Create Date: 2026-10-25 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.config import settings

revision: str = "003_phase3_knowledge"
down_revision: Union[str, None] = "002_phase2_tickets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIMENSION = settings.EMBEDDING_DIMENSION


def upgrade() -> None:
    is_postgres = op.get_bind().dialect.name == "postgresql"

    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        from pgvector.sqlalchemy import Vector

        embedding_column = Vector(EMBEDDING_DIMENSION)
    else:
        embedding_column = sa.Text()

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("source_type", sa.String(length=20), server_default="upload", nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("char_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("embedding_provider", sa.String(length=50), nullable=True),
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
        sa.Column("embedding_dimension", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_documents_id", "knowledge_documents", ["id"], unique=False)
    op.create_index(
        "ix_knowledge_documents_workspace_id", "knowledge_documents", ["workspace_id"], unique=False
    )
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"], unique=False)
    op.create_index(
        "ix_knowledge_documents_workspace_status",
        "knowledge_documents",
        ["workspace_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_documents_workspace_updated",
        "knowledge_documents",
        ["workspace_id", "updated_at"],
        unique=False,
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("embedding", embedding_column, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
    )
    op.create_index("ix_document_chunks_id", "document_chunks", ["id"], unique=False)
    op.create_index(
        "ix_document_chunks_workspace_id", "document_chunks", ["workspace_id"], unique=False
    )
    op.create_index(
        "ix_document_chunks_document_id", "document_chunks", ["document_id"], unique=False
    )
    op.create_index(
        "ix_document_chunks_workspace_document",
        "document_chunks",
        ["workspace_id", "document_id"],
        unique=False,
    )

    if is_postgres:
        # HNSW keeps cosine retrieval fast as a workspace's corpus grows.
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw "
            "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_table("knowledge_documents")
