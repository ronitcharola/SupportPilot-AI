from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import (
    WorkspaceContext,
    require_admin,
    require_support_agent,
    verify_csrf,
)
from app.schemas.knowledge import (
    KnowledgeDocumentDetailResponse,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeStatsResponse,
    KnowledgeTextCreate,
)
from app.services.knowledge_service import (
    create_document_from_text,
    create_document_from_upload,
    delete_document,
    format_document,
    get_document,
    ingest_document,
    knowledge_stats,
    list_documents,
    reset_document_for_reindex,
    search_knowledge,
)
from app.tasks.knowledge_tasks import dispatch_ingestion

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Base"])


async def _index_or_queue(
    db: AsyncSession, workspace_id: str, document_id: str
) -> KnowledgeDocumentResponse:
    """Indexes inline (default) or queues a Celery job, then returns the fresh row."""
    if not dispatch_ingestion(document_id, workspace_id):
        await ingest_document(db, workspace_id, document_id)
    document = await get_document(db, workspace_id, document_id)
    return format_document(document)


@router.get("/documents", response_model=KnowledgeDocumentListResponse)
async def list_knowledge_documents(
    status_filter: Optional[str] = Query(
        None, alias="status", pattern="^(pending|processing|indexed|failed)$"
    ),
    search: Optional[str] = Query(None, max_length=200),
    sort_by: Literal["updated_at", "created_at", "title", "status", "chunk_count"] = Query("updated_at"),
    sort_order: Literal["asc", "desc"] = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Lists knowledge documents for the active workspace."""
    return await list_documents(
        db,
        ctx.workspace_id,
        status_filter=status_filter,
        search=search,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/stats", response_model=KnowledgeStatsResponse)
async def get_knowledge_stats(
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Returns indexing health and embedding configuration for the workspace."""
    return await knowledge_stats(db, ctx.workspace_id)


@router.post(
    "/documents",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def upload_knowledge_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None, max_length=255),
    ctx: WorkspaceContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Uploads a .txt, .md or .pdf document and indexes it (admin only)."""
    data = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    document = await create_document_from_upload(
        db,
        ctx.workspace_id,
        ctx.user_id,
        filename=file.filename or "",
        content_type=file.content_type,
        data=data,
    )
    if title and title.strip():
        if len(title.strip()) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Document titles must be at least 2 characters.",
            )
        document.title = title.strip()[:255]
        await db.commit()

    return await _index_or_queue(db, ctx.workspace_id, document.id)


@router.post(
    "/documents/text",
    response_model=KnowledgeDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def create_text_knowledge_document(
    data: KnowledgeTextCreate,
    ctx: WorkspaceContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Creates a knowledge document from pasted text and indexes it (admin only)."""
    document = await create_document_from_text(
        db,
        ctx.workspace_id,
        ctx.user_id,
        title=data.title,
        content=data.content,
    )
    return await _index_or_queue(db, ctx.workspace_id, document.id)


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentDetailResponse)
async def get_knowledge_document(
    document_id: str,
    include_chunks: bool = Query(False),
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Returns one document; pass include_chunks=true to inspect its chunks."""
    document = await get_document(
        db, ctx.workspace_id, document_id, include_chunks=include_chunks
    )
    return format_document(document, include_chunks=include_chunks)


@router.post(
    "/documents/{document_id}/reindex",
    response_model=KnowledgeDocumentResponse,
    dependencies=[Depends(verify_csrf)],
)
async def reindex_knowledge_document(
    document_id: str,
    ctx: WorkspaceContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Re-chunks and re-embeds an existing document (admin only)."""
    await reset_document_for_reindex(db, ctx.workspace_id, document_id)
    return await _index_or_queue(db, ctx.workspace_id, document_id)


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_csrf)],
)
async def delete_knowledge_document(
    document_id: str,
    ctx: WorkspaceContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Deletes a document and every chunk derived from it (admin only)."""
    await delete_document(db, ctx.workspace_id, document_id)


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search_knowledge_documents(
    data: KnowledgeSearchRequest,
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Retrieval preview: shows which chunks currently ground an answer."""
    return await search_knowledge(
        db,
        ctx.workspace_id,
        data.query,
        top_k=data.top_k,
        threshold=data.threshold,
    )
