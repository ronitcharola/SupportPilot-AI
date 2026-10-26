import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import WorkspaceContext, require_admin
from app.models.ai import AuditLog
from app.schemas.approval import AuditLogListResponse, AuditLogResponse

router = APIRouter(prefix="/api/audit", tags=["Audit"])

CATEGORY_PATTERN = "^(auth|ticket|proposal|workspace|ai)$"


def _format(entry: AuditLog) -> AuditLogResponse:
    details = None
    if entry.details_json:
        try:
            parsed = json.loads(entry.details_json)
            details = parsed if isinstance(parsed, dict) else None
        except (TypeError, ValueError):
            details = None
    return AuditLogResponse(
        id=entry.id,
        event_category=entry.event_category,
        event_type=entry.event_type,
        actor_user_id=entry.actor_user_id,
        actor_email=entry.actor_email,
        target_ticket_id=entry.target_ticket_id,
        target_proposal_id=entry.target_proposal_id,
        details=details,
        ip_address=entry.ip_address,
        user_agent=entry.user_agent,
        created_at=entry.created_at.isoformat() if entry.created_at else "",
    )


@router.get("", response_model=AuditLogListResponse)
async def list_audit_events(
    event_category: Optional[str] = Query(None, pattern=CATEGORY_PATTERN),
    event_type: Optional[str] = Query(None, max_length=100),
    ticket_id: Optional[str] = Query(None),
    proposal_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    ctx: WorkspaceContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Read-only, admin-only, workspace-scoped audit trail.

    There are deliberately no create/update/delete endpoints: rows are written by
    server services only.
    """
    filters = [AuditLog.workspace_id == ctx.workspace_id]
    if event_category:
        filters.append(AuditLog.event_category == event_category)
    if event_type:
        filters.append(AuditLog.event_type == event_type)
    if ticket_id:
        filters.append(AuditLog.target_ticket_id == ticket_id)
    if proposal_id:
        filters.append(AuditLog.target_proposal_id == proposal_id)

    total = (await db.execute(select(func.count(AuditLog.id)).where(*filters))).scalar_one()
    rows = (
        await db.execute(
            select(AuditLog)
            .where(*filters)
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    total_pages = (total + page_size - 1) // page_size if total else 0
    return AuditLogListResponse(
        items=[_format(entry) for entry in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
