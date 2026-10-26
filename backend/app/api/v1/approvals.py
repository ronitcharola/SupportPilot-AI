import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import WorkspaceContext, require_support_agent, verify_csrf
from app.schemas.approval import (
    ApprovalDecision,
    ProposalListResponse,
    ProposalResponse,
    RejectionDecision,
)
from app.services.approval_service import decide_proposal, get_proposal, list_proposals

router = APIRouter(prefix="/api/proposals", tags=["Approvals (HITL)"])

STATUS_PATTERN = "^(pending|approved|rejected|executed|expired)$"
ACTION_PATTERN = "^(issue_refund|cancel_order|apply_discount|flag_account)$"


@router.get("", response_model=ProposalListResponse)
async def list_action_proposals(
    status_filter: Optional[str] = Query(None, alias="status", pattern=STATUS_PATTERN),
    action_type: Optional[str] = Query(None, pattern=ACTION_PATTERN),
    ticket_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Lists workspace-scoped action proposals. Expired pending rows are swept first."""
    return await list_proposals(
        db,
        ctx,
        status_filter=status_filter,
        action_type=action_type,
        ticket_id=ticket_id,
        page=page,
        page_size=page_size,
    )


@router.get("/{id}", response_model=ProposalResponse)
async def get_action_proposal(
    id: str,
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Returns one proposal with its server-computed approval policy."""
    return await get_proposal(db, ctx, id)


@router.post(
    "/{id}/approve",
    response_model=ProposalResponse,
    dependencies=[Depends(verify_csrf)],
)
async def approve_action_proposal(
    id: str,
    data: ApprovalDecision,
    request: Request,
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Records a human approval and executes the action exactly once.

    Requires an idempotency key; replaying the same key returns the original outcome.
    Role limits are re-validated server-side (refunds above the agent limit need an Admin).
    """
    return await decide_proposal(
        db,
        ctx,
        id,
        approve=True,
        idempotency_key=data.idempotency_key,
        note=data.note,
        request=request,
    )


@router.post(
    "/{id}/reject",
    response_model=ProposalResponse,
    dependencies=[Depends(verify_csrf)],
)
async def reject_action_proposal(
    id: str,
    data: RejectionDecision,
    request: Request,
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Rejects a pending proposal without executing it. Nothing is sent to the provider."""
    return await decide_proposal(
        db,
        ctx,
        id,
        approve=False,
        idempotency_key=data.idempotency_key or f"reject-{secrets.token_hex(8)}",
        note=data.note,
        request=request,
    )
