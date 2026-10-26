"""Knowledge base domain logic: ingestion, lifecycle, search and statistics.

Every query is workspace-scoped. Ingestion functions take an explicit
`workspace_id` (instead of a request context) so the same code can run from an
HTTP request, the seed script or a Celery worker.
"""
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.ai.base import EmbeddingProvider, ProviderError
from app.ai.chunking import chunk_text
from app.ai.extractors import ExtractionError, clean_pasted_text, extract_text
from app.ai.retriever import KnowledgeRetriever, RetrievalResult
from app.config import settings
from app.models.knowledge import DocumentChunk, KnowledgeDocument
from app.schemas.knowledge import (
    KnowledgeChunkResponse,
    KnowledgeDocumentDetailResponse,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    KnowledgeSearchHitResponse,
    KnowledgeSearchResponse,
    KnowledgeStatsResponse,
)
from app.services.ai_config import (
    embedding_provider_for_workspace,
    similarity_threshold,
)

logger = logging.getLogger(__name__)

KNOWLEDGE_STATUSES = ("pending", "processing", "indexed", "failed")
EMBEDDING_BATCH_SIZE = 32


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _document_query(workspace_id: str):
    return select(KnowledgeDocument).where(KnowledgeDocument.workspace_id == workspace_id)


async def get_document(
    db: AsyncSession,
    workspace_id: str,
    document_id: str,
    *,
    include_chunks: bool = False,
) -> KnowledgeDocument:
    stmt = _document_query(workspace_id).where(KnowledgeDocument.id == document_id)
    if include_chunks:
        stmt = stmt.options(joinedload(KnowledgeDocument.chunks)).options(
            joinedload(KnowledgeDocument.uploaded_by)
        )
    else:
        stmt = stmt.options(joinedload(KnowledgeDocument.uploaded_by))
    result = await db.execute(stmt)
    document = result.unique().scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge document not found or does not belong to the active workspace.",
        )
    return document


def format_document(document: KnowledgeDocument, *, include_chunks: bool = False):
    payload = dict(
        id=document.id,
        workspace_id=document.workspace_id,
        title=document.title,
        filename=document.filename,
        source_type=document.source_type,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        char_count=document.char_count,
        chunk_count=document.chunk_count,
        status=document.status,
        error_message=document.error_message,
        embedding_provider=document.embedding_provider,
        embedding_model=document.embedding_model,
        embedding_dimension=document.embedding_dimension,
        uploaded_by_user_id=document.uploaded_by_user_id,
        uploaded_by_name=document.uploaded_by.full_name if document.uploaded_by else None,
        indexed_at=document.indexed_at,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )
    if include_chunks:
        chunks = [
            KnowledgeChunkResponse(
                id=chunk.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                char_count=chunk.char_count,
            )
            for chunk in sorted(document.chunks, key=lambda c: c.chunk_index)
        ]
        return KnowledgeDocumentDetailResponse(**payload, chunks=chunks)
    return KnowledgeDocumentResponse(**payload)


async def create_document_from_text(
    db: AsyncSession,
    workspace_id: str,
    user_id: Optional[str],
    *,
    title: str,
    content: str,
    source_type: str = "text",
    filename: Optional[str] = None,
    content_type: str = "text/plain",
) -> KnowledgeDocument:
    """Creates a pending document from already-available text."""
    cleaned = clean_pasted_text(content)
    document = KnowledgeDocument(
        workspace_id=workspace_id,
        title=title.strip(),
        filename=filename,
        source_type=source_type,
        content_type=content_type,
        size_bytes=len(cleaned.encode("utf-8")),
        char_count=len(cleaned),
        source_text=cleaned,
        status="pending",
        uploaded_by_user_id=user_id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def create_document_from_upload(
    db: AsyncSession,
    workspace_id: str,
    user_id: Optional[str],
    *,
    filename: str,
    content_type: Optional[str],
    data: bytes,
) -> KnowledgeDocument:
    """Validates an upload, extracts its text, and creates a pending document."""
    text = extract_text(filename, data)
    title = Path(filename).stem.replace("_", " ").replace("-", " ").strip() or "Untitled document"
    document = KnowledgeDocument(
        workspace_id=workspace_id,
        title=title[:255],
        filename=filename[:255],
        source_type="upload",
        content_type=(content_type or "")[:100] or None,
        size_bytes=len(data),
        char_count=len(text),
        source_text=text,
        status="pending",
        uploaded_by_user_id=user_id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def _mark_failed(
    db: AsyncSession, workspace_id: str, document_id: str, message: str
) -> KnowledgeDocument:
    document = await get_document(db, workspace_id, document_id)
    document.status = "failed"
    document.error_message = message[:1000]
    document.chunk_count = 0
    document.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(document)
    return document


async def ingest_document(
    db: AsyncSession,
    workspace_id: str,
    document_id: str,
) -> KnowledgeDocument:
    """Chunks, embeds and indexes one document. Failures are recorded on the row.

    Returns the document in its final state (`indexed` or `failed`); callers decide
    whether a failed state should be retried.
    """
    document = await get_document(db, workspace_id, document_id)

    try:
        provider, ws_settings = await embedding_provider_for_workspace(db, workspace_id)
    except ProviderError as exc:
        return await _mark_failed(db, workspace_id, document_id, str(exc))

    document.status = "processing"
    document.error_message = None
    document.updated_at = get_utc_now()
    await db.commit()

    try:
        chunks = chunk_text(
            document.source_text or "",
            chunk_size=settings.KNOWLEDGE_CHUNK_SIZE,
            overlap=settings.KNOWLEDGE_CHUNK_OVERLAP,
        )
        if not chunks:
            raise ExtractionError("No indexable text was found in this document.")

        # Replace any previous index atomically with the new one.
        await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.workspace_id == workspace_id,
                DocumentChunk.document_id == document.id,
            )
        )

        vectors: List[List[float]] = []
        contents = [chunk.content for chunk in chunks]
        for start in range(0, len(contents), EMBEDDING_BATCH_SIZE):
            batch = contents[start : start + EMBEDDING_BATCH_SIZE]
            batch_vectors = await provider.embed_documents(batch)
            if len(batch_vectors) != len(batch):
                raise ProviderError("The embedding provider returned an unexpected number of vectors.")
            vectors.extend(batch_vectors)

        now = get_utc_now()
        for chunk, vector in zip(chunks, vectors):
            db.add(
                DocumentChunk(
                    workspace_id=workspace_id,
                    document_id=document.id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    char_count=chunk.char_count,
                    embedding=vector,
                    created_at=now,
                )
            )

        document.chunk_count = len(chunks)
        document.embedding_provider = provider.name
        document.embedding_model = provider.model
        document.embedding_dimension = provider.dimension
        document.status = "indexed"
        document.indexed_at = now
        document.updated_at = now
        await db.commit()
        await db.refresh(document)
        logger.info(
            "Indexed knowledge document %s in workspace %s (%s chunks, %s provider)",
            document.id,
            workspace_id,
            document.chunk_count,
            provider.name,
        )
        return document

    except (ExtractionError, ProviderError) as exc:
        await db.rollback()
        return await _mark_failed(db, workspace_id, document_id, str(exc))
    except Exception:
        await db.rollback()
        logger.exception("Unexpected error while indexing document %s", document_id)
        return await _mark_failed(
            db, workspace_id, document_id, "Indexing failed due to an internal error."
        )


async def list_documents(
    db: AsyncSession,
    workspace_id: str,
    *,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
) -> KnowledgeDocumentListResponse:
    filters = [KnowledgeDocument.workspace_id == workspace_id]
    if status_filter:
        filters.append(KnowledgeDocument.status == status_filter)
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        filters.append(
            func.lower(KnowledgeDocument.title).like(term)
            | func.lower(func.coalesce(KnowledgeDocument.filename, "")).like(term)
        )

    total = (
        await db.execute(select(func.count(KnowledgeDocument.id)).where(*filters))
    ).scalar_one()

    sort_columns = {
        "created_at": KnowledgeDocument.created_at,
        "updated_at": KnowledgeDocument.updated_at,
        "title": KnowledgeDocument.title,
        "status": KnowledgeDocument.status,
        "chunk_count": KnowledgeDocument.chunk_count,
    }
    sort_column = sort_columns.get(sort_by, KnowledgeDocument.updated_at)
    order = sort_column.asc() if sort_order == "asc" else sort_column.desc()

    stmt = (
        select(KnowledgeDocument)
        .where(*filters)
        .options(joinedload(KnowledgeDocument.uploaded_by))
        .order_by(order, KnowledgeDocument.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    documents = (await db.execute(stmt)).unique().scalars().all()
    total_pages = (total + page_size - 1) // page_size if total else 0

    return KnowledgeDocumentListResponse(
        items=[format_document(document) for document in documents],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def delete_document(db: AsyncSession, workspace_id: str, document_id: str) -> None:
    document = await get_document(db, workspace_id, document_id)
    await db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.workspace_id == workspace_id,
            DocumentChunk.document_id == document.id,
        )
    )
    await db.delete(document)
    await db.commit()


async def reset_document_for_reindex(
    db: AsyncSession, workspace_id: str, document_id: str
) -> KnowledgeDocument:
    document = await get_document(db, workspace_id, document_id)
    if document.status == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This document is already being indexed. Wait for it to finish and try again.",
        )
    document.status = "pending"
    document.error_message = None
    document.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(document)
    return document


async def build_retriever(
    db: AsyncSession, workspace_id: str, threshold: Optional[float] = None
) -> Tuple[KnowledgeRetriever, float, str]:
    """Builds a retriever plus the effective threshold and provider name."""
    provider: EmbeddingProvider
    provider, ws_settings = await embedding_provider_for_workspace(db, workspace_id)
    effective_threshold = (
        threshold
        if threshold is not None
        else similarity_threshold(provider.name, ws_settings)
    )
    retriever = KnowledgeRetriever(db, workspace_id, provider, effective_threshold)
    return retriever, effective_threshold, provider.name


async def search_knowledge(
    db: AsyncSession,
    workspace_id: str,
    query: str,
    *,
    top_k: int = 5,
    threshold: Optional[float] = None,
) -> KnowledgeSearchResponse:
    """Staff-facing retrieval preview; never crosses the workspace boundary."""
    started = time.perf_counter()
    retriever, _, _ = await build_retriever(db, workspace_id, threshold)
    result = await retriever.retrieve(query, top_k=top_k)

    return KnowledgeSearchResponse(
        query=query,
        results=[
            KnowledgeSearchHitResponse(
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                document_title=hit.document_title,
                chunk_index=hit.chunk_index,
                excerpt=hit.content[:600],
                score=hit.score,
            )
            for hit in result.chunks
        ],
        candidates_scanned=result.candidates_scanned,
        threshold=result.threshold,
        provider=result.provider,
        took_ms=int((time.perf_counter() - started) * 1000),
    )


async def knowledge_stats(db: AsyncSession, workspace_id: str) -> KnowledgeStatsResponse:
    status_rows = await db.execute(
        select(KnowledgeDocument.status, func.count(KnowledgeDocument.id))
        .where(KnowledgeDocument.workspace_id == workspace_id)
        .group_by(KnowledgeDocument.status)
    )
    counts = {row[0]: row[1] for row in status_rows.all()}

    total_chunks = (
        await db.execute(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.workspace_id == workspace_id)
        )
    ).scalar_one()
    total_characters = (
        await db.execute(
            select(func.coalesce(func.sum(KnowledgeDocument.char_count), 0)).where(
                KnowledgeDocument.workspace_id == workspace_id
            )
        )
    ).scalar_one()

    provider, ws_settings = await embedding_provider_for_workspace(db, workspace_id)
    return KnowledgeStatsResponse(
        total_documents=sum(counts.values()),
        indexed_documents=counts.get("indexed", 0),
        processing_documents=counts.get("pending", 0) + counts.get("processing", 0),
        failed_documents=counts.get("failed", 0),
        total_chunks=total_chunks,
        total_characters=total_characters,
        embedding_provider=provider.name,
        embedding_dimension=provider.dimension,
        similarity_threshold=similarity_threshold(provider.name, ws_settings),
        retrieval_scan_limit=settings.RETRIEVAL_SCAN_LIMIT,
    )


async def document_source_preview(
    db: AsyncSession, workspace_id: str, document_id: str, limit: int = 800
) -> str:
    document = await get_document(db, workspace_id, document_id)
    return (document.source_text or "")[:limit]
