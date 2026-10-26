"""AI-side consequential action tools — the only AI path to a consequential action.

Every tool here creates an `action_proposals` row in `pending` status. None of them
can approve, reject or execute anything: execution lives in
`app/services/action_executor.py`, which this package never imports. A human must
decide through the approval API before anything happens.

The strict param validation in `policy_engine.validate_action_params` (via
`create_pending_proposal`) means a malformed LLM tool call is rejected with 422 and
never reaches the queue with surprising parameters.
"""
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import ActionProposal
from app.services.approval_service import create_pending_proposal


async def _propose(
    db: AsyncSession,
    *,
    workspace_id: str,
    ticket_id: str,
    action_type: str,
    params: Dict[str, Any],
    rationale: str,
    provider: Optional[str],
    confidence: Optional[float],
) -> ActionProposal:
    proposal, _ticket = await create_pending_proposal(
        db,
        workspace_id=workspace_id,
        ticket_id=ticket_id,
        action_type=action_type,
        params=params,
        rationale=rationale,
        ai_confidence=confidence,
        provider=provider,
        actor=None,
        source="ai_tool",
    )
    await db.commit()
    return proposal


async def propose_refund(
    db: AsyncSession,
    *,
    workspace_id: str,
    ticket_id: str,
    amount: float,
    reason: str,
    rationale: str,
    currency: str = "USD",
    provider: Optional[str] = None,
    confidence: Optional[float] = None,
) -> ActionProposal:
    return await _propose(
        db,
        workspace_id=workspace_id,
        ticket_id=ticket_id,
        action_type="issue_refund",
        params={"amount": amount, "currency": currency, "reason": reason},
        rationale=rationale,
        provider=provider,
        confidence=confidence,
    )


async def propose_order_cancellation(
    db: AsyncSession,
    *,
    workspace_id: str,
    ticket_id: str,
    order_id: str,
    reason: str,
    rationale: str,
    provider: Optional[str] = None,
    confidence: Optional[float] = None,
) -> ActionProposal:
    return await _propose(
        db,
        workspace_id=workspace_id,
        ticket_id=ticket_id,
        action_type="cancel_order",
        params={"order_id": order_id, "reason": reason},
        rationale=rationale,
        provider=provider,
        confidence=confidence,
    )


async def propose_discount(
    db: AsyncSession,
    *,
    workspace_id: str,
    ticket_id: str,
    percent: float,
    reason: str,
    rationale: str,
    duration_days: int = 30,
    provider: Optional[str] = None,
    confidence: Optional[float] = None,
) -> ActionProposal:
    return await _propose(
        db,
        workspace_id=workspace_id,
        ticket_id=ticket_id,
        action_type="apply_discount",
        params={"percent": percent, "duration_days": duration_days, "reason": reason},
        rationale=rationale,
        provider=provider,
        confidence=confidence,
    )


async def propose_account_flag(
    db: AsyncSession,
    *,
    workspace_id: str,
    ticket_id: str,
    reason: str,
    rationale: str,
    severity: str = "medium",
    provider: Optional[str] = None,
    confidence: Optional[float] = None,
) -> ActionProposal:
    return await _propose(
        db,
        workspace_id=workspace_id,
        ticket_id=ticket_id,
        action_type="flag_account",
        params={"severity": severity, "reason": reason},
        rationale=rationale,
        provider=provider,
        confidence=confidence,
    )
