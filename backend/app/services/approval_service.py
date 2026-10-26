"""Human-in-the-loop approval service (Phase 5).

Architectural guarantees:
- Creating a proposal only ever writes `action_proposals` in `pending`; the AI layer
  calls this service through `app/ai/tools.py` and cannot execute anything.
- Only `decide_proposal` executes an action, and only after a human decision has been
  recorded in the same transaction.
- The decision is guarded by `SELECT ... FOR UPDATE` on databases that support it plus
  an atomic `UPDATE ... WHERE status = 'pending'` conditional transition, so two
  reviewers cannot both execute the same proposal (SQLite ignores FOR UPDATE, the
  conditional update still serializes the winner).
- Every approval, rejection, expiry and execution writes an append-only audit event.
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import WorkspaceContext
from app.models.ai import ActionProposal
from app.models.base import get_utc_now
from app.models.ticket import Ticket
from app.models.user import User
from app.models.workspace import WorkspaceSettings
from app.schemas.approval import (
    ProposalCreate,
    ProposalListResponse,
    ProposalPolicy,
    ProposalResponse,
)
from app.services.action_executor import execute_approved_action
from app.services.audit_service import record_audit_event
from app.services.policy_engine import (
    approval_policy,
    assert_role_can_decide,
    validate_action_params,
)
from app.services.ticket_service import allowed_transitions

MAX_PAGE_SIZE = 100


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite returns naive datetimes; treat them as UTC for expiry comparisons."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _iso(value: Optional[datetime]) -> Optional[str]:
    aware = _as_utc(value)
    return aware.isoformat() if aware else None


def _load_json(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except (TypeError, ValueError):
        return None


def _format_proposal(
    proposal: ActionProposal,
    ticket: Optional[Ticket] = None,
    reviewer_name: Optional[str] = None,
    *,
    replayed: bool = False,
) -> ProposalResponse:
    params = _load_json(proposal.action_params_json) or {}
    policy = approval_policy(proposal.action_type, params)

    if ticket is None:
        # Never lazy-load a relationship here: these methods run in async contexts
        # where an implicit IO call would raise MissingGreenlet.
        ticket = proposal.__dict__.get("ticket")

    return ProposalResponse(
        id=proposal.id,
        workspace_id=proposal.workspace_id,
        ticket_id=proposal.ticket_id,
        ticket_number=ticket.ticket_number if ticket else None,
        ticket_subject=ticket.subject if ticket else None,
        action_type=proposal.action_type,
        params=params,
        rationale=proposal.rationale,
        ai_confidence=proposal.ai_confidence,
        proposed_by_ai_provider=proposal.proposed_by_ai_provider,
        status=proposal.status,
        policy=ProposalPolicy(**policy.model_dump()),
        reviewed_by_user_id=proposal.reviewed_by_user_id,
        reviewed_by_name=reviewer_name
        or (proposal.reviewed_by.full_name if getattr(proposal, "reviewed_by", None) else None),
        reviewed_at=_iso(proposal.reviewed_at),
        reviewer_note=proposal.reviewer_note,
        execution_result=_load_json(proposal.execution_result_json),
        executed_at=_iso(proposal.executed_at),
        expires_at=_iso(proposal.expires_at),
        created_at=_iso(proposal.created_at) or "",
        replayed=replayed,
    )


async def _get_scoped_ticket(db: AsyncSession, workspace_id: str, ticket_id: str) -> Ticket:
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id, Ticket.workspace_id == workspace_id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found in this workspace.",
        )
    return ticket


async def _proposal_expiry_hours(db: AsyncSession, workspace_id: str) -> int:
    result = await db.execute(
        select(WorkspaceSettings.proposal_expiry_hours).where(
            WorkspaceSettings.workspace_id == workspace_id
        )
    )
    hours = result.scalar_one_or_none()
    return int(hours or settings.PROPOSAL_DEFAULT_EXPIRY_HOURS)


async def create_pending_proposal(
    db: AsyncSession,
    *,
    workspace_id: str,
    ticket_id: str,
    action_type: str,
    params: Dict[str, Any],
    rationale: str,
    ai_confidence: Optional[float] = None,
    provider: Optional[str] = None,
    actor: Optional[User] = None,
    request: Optional[Request] = None,
    source: str = "api",
) -> Tuple[ActionProposal, Ticket]:
    """Creates a pending proposal. The caller owns the commit."""
    ticket = await _get_scoped_ticket(db, workspace_id, ticket_id)

    if "pending_approval" not in allowed_transitions(ticket.status):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A consequential action cannot be proposed while the ticket is "
                f"'{ticket.status}'. Move it to open, in progress or escalated first."
            ),
        )

    validated_params = validate_action_params(action_type, params)
    expiry_hours = await _proposal_expiry_hours(db, workspace_id)
    now = get_utc_now()

    proposal_provider = provider
    if not proposal_provider:
        ws_provider = await db.execute(
            select(WorkspaceSettings.llm_provider).where(WorkspaceSettings.workspace_id == workspace_id)
        )
        proposal_provider = ws_provider.scalar_one_or_none() or settings.LLM_PROVIDER

    proposal = ActionProposal(
        workspace_id=workspace_id,
        ticket_id=ticket.id,
        proposed_by_ai_provider=proposal_provider,
        action_type=action_type,
        action_params_json=json.dumps(validated_params),
        rationale=rationale,
        ai_confidence=ai_confidence,
        status="pending",
        created_at=now,
        expires_at=now + timedelta(hours=expiry_hours),
    )
    db.add(proposal)
    await db.flush()

    ticket.status = "pending_approval"
    ticket.updated_at = now

    await record_audit_event(
        db,
        workspace_id=workspace_id,
        event_category="proposal",
        event_type="proposal_created",
        actor=actor,
        ticket_id=ticket.id,
        proposal_id=proposal.id,
        details={
            "action_type": action_type,
            "params": validated_params,
            "source": source,
            "expires_at": _iso(proposal.expires_at),
        },
        request=request,
    )
    return proposal, ticket


async def create_ticket_proposal(
    db: AsyncSession,
    ctx: WorkspaceContext,
    ticket_id: str,
    data: ProposalCreate,
    request: Optional[Request] = None,
) -> ProposalResponse:
    proposal, ticket = await create_pending_proposal(
        db,
        workspace_id=ctx.workspace_id,
        ticket_id=ticket_id,
        action_type=data.action_type,
        params=data.params,
        rationale=data.rationale,
        ai_confidence=data.ai_confidence,
        actor=ctx.user,
        request=request,
    )
    await db.commit()
    return _format_proposal(proposal, ticket, reviewer_name=None)


async def get_proposal(db: AsyncSession, ctx: WorkspaceContext, proposal_id: str) -> ProposalResponse:
    result = await db.execute(
        select(ActionProposal, Ticket, User.full_name)
        .join(Ticket, ActionProposal.ticket_id == Ticket.id)
        .outerjoin(User, ActionProposal.reviewed_by_user_id == User.id)
        .where(
            ActionProposal.id == proposal_id,
            ActionProposal.workspace_id == ctx.workspace_id,
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found in this workspace.",
        )
    proposal, ticket, reviewer_name = row
    return _format_proposal(proposal, ticket, reviewer_name)


async def expire_stale_proposals(db: AsyncSession, workspace_id: str) -> int:
    """Marks pending proposals past their expiry and audits each. The caller commits."""
    result = await db.execute(
        select(ActionProposal).where(
            ActionProposal.workspace_id == workspace_id,
            ActionProposal.status == "pending",
            ActionProposal.expires_at.is_not(None),
        )
    )
    now = get_utc_now()
    expired = 0
    for proposal in result.scalars().all():
        expires_at = _as_utc(proposal.expires_at)
        if expires_at and expires_at <= now:
            proposal.status = "expired"
            expired += 1
            await record_audit_event(
                db,
                workspace_id=workspace_id,
                event_category="proposal",
                event_type="proposal_expired",
                ticket_id=proposal.ticket_id,
                proposal_id=proposal.id,
                details={"action_type": proposal.action_type, "expired_at": _iso(expires_at)},
            )
    return expired


async def list_proposals(
    db: AsyncSession,
    ctx: WorkspaceContext,
    *,
    status_filter: Optional[str] = None,
    action_type: Optional[str] = None,
    ticket_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> ProposalListResponse:
    if await expire_stale_proposals(db, ctx.workspace_id):
        await db.commit()

    filters = [ActionProposal.workspace_id == ctx.workspace_id]
    if status_filter:
        filters.append(ActionProposal.status == status_filter)
    if action_type:
        filters.append(ActionProposal.action_type == action_type)
    if ticket_id:
        filters.append(ActionProposal.ticket_id == ticket_id)

    total = (
        await db.execute(select(func.count(ActionProposal.id)).where(*filters))
    ).scalar_one()

    stmt = (
        select(ActionProposal, Ticket, User.full_name)
        .join(Ticket, ActionProposal.ticket_id == Ticket.id)
        .outerjoin(User, ActionProposal.reviewed_by_user_id == User.id)
        .where(*filters)
        .order_by(ActionProposal.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()

    counts_rows = (
        await db.execute(
            select(ActionProposal.status, func.count(ActionProposal.id))
            .where(ActionProposal.workspace_id == ctx.workspace_id)
            .group_by(ActionProposal.status)
        )
    ).all()
    status_counts = {name: 0 for name in ["pending", "approved", "rejected", "executed", "expired"]}
    for name, count in counts_rows:
        status_counts[name] = count

    total_pages = (total + page_size - 1) // page_size if total else 0

    return ProposalListResponse(
        items=[_format_proposal(proposal, ticket, reviewer) for proposal, ticket, reviewer in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        status_counts=status_counts,
    )


def _decision_filters(proposal_id: str, workspace_id: str):
    return [ActionProposal.id == proposal_id, ActionProposal.workspace_id == workspace_id]


async def _conditional_decision(
    db: AsyncSession,
    *,
    proposal_id: str,
    workspace_id: str,
    values: Dict[str, Any],
) -> bool:
    """Atomic pending → decided transition. Returns False if another reviewer won."""
    result = await db.execute(
        update(ActionProposal)
        .where(
            *_decision_filters(proposal_id, workspace_id),
            ActionProposal.status == "pending",
        )
        .values(**values)
    )
    return result.rowcount == 1


async def decide_proposal(
    db: AsyncSession,
    ctx: WorkspaceContext,
    proposal_id: str,
    *,
    approve: bool,
    idempotency_key: str,
    note: Optional[str] = None,
    request: Optional[Request] = None,
) -> ProposalResponse:
    result = await db.execute(
        select(ActionProposal)
        .where(*_decision_filters(proposal_id, ctx.workspace_id))
        .with_for_update()
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found in this workspace.",
        )

    ticket = (
        await db.execute(
            select(Ticket).where(
                Ticket.id == proposal.ticket_id,
                Ticket.workspace_id == ctx.workspace_id,
            )
        )
    ).scalar_one_or_none()

    # Replaying the exact same decision key returns the original outcome.
    if proposal.idempotency_key and proposal.idempotency_key == idempotency_key:
        if proposal.status in ("approved", "executed", "rejected"):
            return _format_proposal(
                proposal, ticket, reviewer_name=ctx.user.full_name, replayed=True
            )

    if proposal.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This proposal was already decided (status: {proposal.status}).",
        )

    # A key that already belongs to a different proposal must not be reused.
    duplicate_key = await db.execute(
        select(ActionProposal.id).where(
            ActionProposal.idempotency_key == idempotency_key,
            ActionProposal.id != proposal.id,
        )
    )
    if duplicate_key.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This idempotency key was already used for another approval.",
        )

    expires_at = _as_utc(proposal.expires_at)
    now = get_utc_now()
    if expires_at and expires_at <= now:
        proposal.status = "expired"
        await record_audit_event(
            db,
            workspace_id=ctx.workspace_id,
            event_category="proposal",
            event_type="proposal_expired",
            actor=ctx.user,
            ticket_id=proposal.ticket_id,
            proposal_id=proposal.id,
            details={"action_type": proposal.action_type, "expired_at": _iso(expires_at)},
            request=request,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This proposal has expired. Create a new proposal after re-verifying the case.",
        )

    params = _load_json(proposal.action_params_json) or {}
    # Never trust stored params either: re-validate before any role/execution decision.
    validated_params = validate_action_params(proposal.action_type, params)

    if approve:
        assert_role_can_decide(ctx.role, proposal.action_type, validated_params)

    decided_values: Dict[str, Any] = {
        "status": "rejected" if not approve else "approved",
        "reviewed_by_user_id": ctx.user.id,
        "reviewed_at": now,
        "reviewer_note": note,
        "idempotency_key": idempotency_key,
    }
    won = await _conditional_decision(
        db,
        proposal_id=proposal.id,
        workspace_id=ctx.workspace_id,
        values=decided_values,
    )
    if not won:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another reviewer already decided this proposal.",
        )

    await db.refresh(proposal)

    if not approve:
        await record_audit_event(
            db,
            workspace_id=ctx.workspace_id,
            event_category="proposal",
            event_type="proposal_rejected",
            actor=ctx.user,
            ticket_id=proposal.ticket_id,
            proposal_id=proposal.id,
            details={
                "action_type": proposal.action_type,
                "params": validated_params,
                "note": note,
            },
            request=request,
        )
        await _release_ticket(db, proposal.ticket_id, ctx.workspace_id)
        await db.commit()
        return _format_proposal(proposal, ticket, reviewer_name=ctx.user.full_name)

    proposal.status = "approved"
    await record_audit_event(
        db,
        workspace_id=ctx.workspace_id,
        event_category="proposal",
        event_type="proposal_approved",
        actor=ctx.user,
        ticket_id=proposal.ticket_id,
        proposal_id=proposal.id,
        details={
            "action_type": proposal.action_type,
            "params": validated_params,
            "note": note,
            "role": ctx.role,
        },
        request=request,
    )

    try:
        receipt = execute_approved_action(proposal, validated_params)
    except Exception as exc:  # pragma: no cover - defensive; mock executor is deterministic
        proposal.status = "approved"
        await record_audit_event(
            db,
            workspace_id=ctx.workspace_id,
            event_category="proposal",
            event_type="proposal_execution_failed",
            actor=ctx.user,
            ticket_id=proposal.ticket_id,
            proposal_id=proposal.id,
            details={"action_type": proposal.action_type, "error": str(exc)[:500]},
            request=request,
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The approved action failed during execution. It was not retried automatically.",
        ) from exc

    proposal.status = "executed"
    proposal.executed_at = now
    proposal.execution_result_json = json.dumps(receipt)

    await record_audit_event(
        db,
        workspace_id=ctx.workspace_id,
        event_category="proposal",
        event_type="proposal_executed",
        actor=ctx.user,
        ticket_id=proposal.ticket_id,
        proposal_id=proposal.id,
        details={
            "action_type": proposal.action_type,
            "reference": receipt.get("reference"),
            "status": receipt.get("status"),
        },
        request=request,
    )
    await _release_ticket(db, proposal.ticket_id, ctx.workspace_id)
    await db.commit()

    return _format_proposal(proposal, ticket, reviewer_name=ctx.user.full_name)


async def _release_ticket(db: AsyncSession, ticket_id: str, workspace_id: str) -> None:
    """Returns a ticket to active work once its proposal is decided."""
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id, Ticket.workspace_id == workspace_id)
    )
    ticket = result.scalar_one_or_none()
    if ticket and ticket.status == "pending_approval":
        ticket.status = "in_progress"
        ticket.updated_at = get_utc_now()
