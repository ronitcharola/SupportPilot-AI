from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import WorkspaceContext, require_support_agent
from app.models.ticket import Ticket
from app.models.ai import ActionProposal, AuditLog

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/overview", summary="Get Dashboard Analytics Overview")
async def get_analytics_overview(
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get dashboard analytics overview with KPI counts and category distribution.

    Workspace-scoped: every query is filtered by the authenticated workspace context.
    """
    ws = ctx.workspace_id

    # Total tickets in workspace
    total_tickets = (await db.execute(
        select(func.count(Ticket.id)).where(Ticket.workspace_id == ws)
    )).scalar_one()

    # Open tickets
    open_tickets = (await db.execute(
        select(func.count(Ticket.id)).where(Ticket.workspace_id == ws, Ticket.status == "open")
    )).scalar_one()

    # In-progress tickets
    in_progress_tickets = (await db.execute(
        select(func.count(Ticket.id)).where(Ticket.workspace_id == ws, Ticket.status == "in_progress")
    )).scalar_one()

    # Resolved tickets
    resolved_tickets = (await db.execute(
        select(func.count(Ticket.id)).where(Ticket.workspace_id == ws, Ticket.status == "resolved")
    )).scalar_one()

    # Closed tickets
    closed_tickets = (await db.execute(
        select(func.count(Ticket.id)).where(Ticket.workspace_id == ws, Ticket.status == "closed")
    )).scalar_one()

    # Escalated tickets (is_escalated flag or status = escalated)
    escalated_tickets = (await db.execute(
        select(func.count(Ticket.id)).where(
            Ticket.workspace_id == ws,
            (Ticket.status == "escalated") | (Ticket.is_escalated == True),
        )
    )).scalar_one()

    # Pending approvals - tickets with pending_approval status
    pending_approval_tickets = (await db.execute(
        select(func.count(Ticket.id)).where(Ticket.workspace_id == ws, Ticket.status == "pending_approval")
    )).scalar_one()

    # Pending action proposals
    pending_proposals = (await db.execute(
        select(func.count(ActionProposal.id)).where(
            ActionProposal.workspace_id == ws, ActionProposal.status == "pending"
        )
    )).scalar_one()

    # Category distribution
    category_result = await db.execute(
        select(Ticket.category, func.count(Ticket.id))
        .where(Ticket.workspace_id == ws, Ticket.category.isnot(None))
        .group_by(Ticket.category)
    )
    category_distribution = [
        {"category": row[0] or "uncategorized", "count": int(row[1])}
        for row in category_result.all()
    ]

    # Status distribution
    status_result = await db.execute(
        select(Ticket.status, func.count(Ticket.id))
        .where(Ticket.workspace_id == ws)
        .group_by(Ticket.status)
    )
    status_distribution = [
        {"status": row[0], "count": int(row[1])}
        for row in status_result.all()
    ]

    # Priority distribution
    priority_result = await db.execute(
        select(Ticket.priority, func.count(Ticket.id))
        .where(Ticket.workspace_id == ws)
        .group_by(Ticket.priority)
    )
    priority_distribution = [
        {"priority": row[0], "count": int(row[1])}
        for row in priority_result.all()
    ]

    # AI sentiment distribution
    sentiment_result = await db.execute(
        select(Ticket.ai_sentiment, func.count(Ticket.id))
        .where(Ticket.workspace_id == ws, Ticket.ai_sentiment.isnot(None))
        .group_by(Ticket.ai_sentiment)
    )
    sentiment_distribution = [
        {"sentiment": row[0], "count": int(row[1])}
        for row in sentiment_result.all()
    ]

    # Proposal status counts
    proposal_status_result = await db.execute(
        select(ActionProposal.status, func.count(ActionProposal.id))
        .where(ActionProposal.workspace_id == ws)
        .group_by(ActionProposal.status)
    )
    proposal_status_counts = {row[0]: int(row[1]) for row in proposal_status_result.all()}

    # Recent audit event count (last 24h)
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_audit_count = (await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.workspace_id == ws, AuditLog.created_at >= cutoff
        )
    )).scalar_one()

    return {
        "total_tickets": int(total_tickets),
        "open_tickets": int(open_tickets),
        "in_progress_tickets": int(in_progress_tickets),
        "resolved_tickets": int(resolved_tickets),
        "closed_tickets": int(closed_tickets),
        "escalated_tickets": int(escalated_tickets),
        "pending_approval_tickets": int(pending_approval_tickets),
        "pending_proposals": int(pending_proposals),
        "recent_audit_events_24h": int(recent_audit_count),
        "proposal_status_counts": proposal_status_counts,
        "category_distribution": category_distribution,
        "status_distribution": status_distribution,
        "priority_distribution": priority_distribution,
        "sentiment_distribution": sentiment_distribution,
    }