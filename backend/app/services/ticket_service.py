import json
from datetime import datetime, timezone
from typing import Optional, List, Sequence
from sqlalchemy import select, func, or_, desc, asc, case
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.ai.base import ProviderError
from app.models.ticket import Ticket, TicketMessage, TicketAssignment
from app.models.user import User, Customer
from app.models.workspace import WorkspaceMembership
from app.services.triage_service import apply_ai_triage, build_ticket_conversation
from app.schemas.ticket import (
    TicketCreate,
    TicketUpdate,
    TicketResponse,
    TicketListResponse,
    MessageResponse,
    AssignTicketRequest,
)
from app.dependencies import WorkspaceContext

TICKET_STATUSES = [
    "open",
    "in_progress",
    "pending_approval",
    "waiting_for_customer",
    "escalated",
    "resolved",
    "closed",
]

TICKET_PRIORITIES = ["low", "medium", "high", "urgent"]

TICKET_CATEGORIES = [
    "billing",
    "refunds",
    "technical_issues",
    "account_access",
    "orders",
    "shipping",
    "product_questions",
    "other",
]

# Explicit, server-enforced status lifecycle. Anything not listed here is rejected.
STATUS_TRANSITIONS: dict[str, List[str]] = {
    "open": ["in_progress", "pending_approval", "waiting_for_customer", "escalated", "resolved", "closed"],
    "in_progress": ["open", "pending_approval", "waiting_for_customer", "escalated", "resolved", "closed"],
    "pending_approval": ["in_progress", "escalated", "resolved", "closed"],
    "waiting_for_customer": ["in_progress", "escalated", "resolved", "closed"],
    "escalated": ["in_progress", "waiting_for_customer", "resolved", "closed"],
    "resolved": ["open", "closed"],
    "closed": ["open"],
}

PRIORITY_SORT_RANK = case(
    {"urgent": 4, "high": 3, "medium": 2, "low": 1},
    value=Ticket.priority,
    else_=0,
)

STATUS_SORT_RANK = case(
    {name: index for index, name in enumerate(TICKET_STATUSES)},
    value=Ticket.status,
    else_=len(TICKET_STATUSES),
)


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


def allowed_transitions(current_status: str) -> List[str]:
    """Statuses the ticket may legally move to from its current state (self-transition excluded)."""
    return list(STATUS_TRANSITIONS.get(current_status, []))


def validate_status_transition(current_status: str, new_status: str) -> None:
    """Raises HTTP 409 when a requested status change is not part of the lifecycle."""
    if new_status == current_status:
        return
    if new_status not in TICKET_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown ticket status '{new_status}'.",
        )
    permitted = STATUS_TRANSITIONS.get(current_status, [])
    if new_status not in permitted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invalid status transition from '{current_status}' to '{new_status}'. "
                f"Allowed transitions: {', '.join(permitted) if permitted else 'none'}."
            ),
        )


def format_message_response(msg: TicketMessage) -> MessageResponse:
    sender_name = "System"
    if msg.sender_type == "agent" and msg.sender_user:
        sender_name = msg.sender_user.full_name
    elif msg.sender_type == "customer" and msg.sender_customer:
        sender_name = msg.sender_customer.name
    elif msg.sender_type == "ai":
        sender_name = "SupportPilot AI"

    return MessageResponse(
        id=msg.id,
        ticket_id=msg.ticket_id,
        sender_type=msg.sender_type,
        sender_name=sender_name,
        body=msg.body,
        is_internal_note=msg.is_internal_note,
        created_at=msg.created_at,
        metadata_json=msg.metadata_json,
    )


def _ai_classification(ticket: Ticket) -> dict:
    if not ticket.ai_classification_json:
        return {}
    try:
        data = json.loads(ticket.ai_classification_json)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def format_ticket_response(
    ticket: Ticket,
    include_internal_notes: bool = True,
    include_ai_metadata: bool = True,
) -> TicketResponse:
    msgs = []
    if ticket.messages:
        for m in ticket.messages:
            if not include_internal_notes and m.is_internal_note:
                continue
            msgs.append(format_message_response(m))

    classification = _ai_classification(ticket) if include_ai_metadata else {}
    escalation_reasons = (
        [reason for reason in classification.get("escalation_reasons", []) if isinstance(reason, str)]
        if include_ai_metadata
        else []
    )

    return TicketResponse(
        id=ticket.id,
        workspace_id=ticket.workspace_id,
        ticket_number=ticket.ticket_number,
        subject=ticket.subject,
        description=ticket.description,
        status=ticket.status,
        priority=ticket.priority,
        category=ticket.category,
        customer_id=ticket.customer_id,
        customer_name=ticket.customer.name if ticket.customer else "Unknown",
        customer_email=ticket.customer.email if ticket.customer else "unknown@customer.com",
        assigned_agent_id=ticket.assigned_agent_id,
        assigned_agent_name=ticket.assigned_agent.full_name if ticket.assigned_agent else None,
        ai_intent=ticket.ai_intent if include_ai_metadata else None,
        ai_confidence=ticket.ai_confidence if include_ai_metadata else None,
        ai_sentiment=ticket.ai_sentiment if include_ai_metadata else None,
        ai_summary=ticket.ai_summary if include_ai_metadata else None,
        ai_urgency_score=ticket.ai_urgency_score if include_ai_metadata else None,
        ai_escalation_reasons=escalation_reasons,
        ai_suggested_category=classification.get("category") if include_ai_metadata else None,
        ai_suggested_priority=classification.get("priority") if include_ai_metadata else None,
        is_escalated=ticket.is_escalated if include_ai_metadata else False,
        escalation_reason=ticket.escalation_reason if include_ai_metadata else None,
        resolved_at=ticket.resolved_at,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        allowed_transitions=allowed_transitions(ticket.status),
        messages=msgs,
    )


async def list_workspace_tickets(
    db: AsyncSession,
    ctx: WorkspaceContext,
    status_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    assignee_id: Optional[str] = None,
    unassigned: bool = False,
    assigned_to_me: bool = False,
    escalated: bool = False,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> TicketListResponse:
    filters = [Ticket.workspace_id == ctx.workspace_id]
    needs_customer_join = False

    if status_filter:
        filters.append(Ticket.status == status_filter)
    if priority_filter:
        filters.append(Ticket.priority == priority_filter)
    if category_filter:
        filters.append(Ticket.category == category_filter)
    if assigned_to_me:
        filters.append(Ticket.assigned_agent_id == ctx.user_id)
    elif assignee_id:
        filters.append(Ticket.assigned_agent_id == assignee_id)
    elif unassigned:
        filters.append(Ticket.assigned_agent_id.is_(None))
    if escalated:
        filters.append(Ticket.is_escalated.is_(True))

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        needs_customer_join = True
        filters.append(
            or_(
                func.lower(Ticket.subject).like(term),
                func.lower(Ticket.description).like(term),
                func.lower(Customer.name).like(term),
                func.lower(Customer.email).like(term),
            )
        )

    # Count matching rows (workspace-scoped, before pagination)
    count_stmt = select(func.count(Ticket.id)).where(*filters)
    data_stmt = (
        select(Ticket)
        .where(*filters)
        .options(
            joinedload(Ticket.customer),
            joinedload(Ticket.assigned_agent),
            selectinload(Ticket.messages).options(
                joinedload(TicketMessage.sender_user),
                joinedload(TicketMessage.sender_customer),
            ),
        )
    )
    if needs_customer_join:
        count_stmt = count_stmt.join(Customer, Ticket.customer_id == Customer.id)
        data_stmt = data_stmt.join(Customer, Ticket.customer_id == Customer.id)

    total_count = (await db.execute(count_stmt)).scalar_one()

    sort_columns = {
        "created_at": Ticket.created_at,
        "updated_at": Ticket.updated_at,
        "ticket_number": Ticket.ticket_number,
        "priority": PRIORITY_SORT_RANK,
        "status": STATUS_SORT_RANK,
        "subject": Ticket.subject,
    }
    sort_column = sort_columns.get(sort_by, Ticket.created_at)
    direction = asc if sort_order.lower() == "asc" else desc

    data_stmt = (
        data_stmt.order_by(direction(sort_column), desc(Ticket.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(data_stmt)
    tickets = result.unique().scalars().all()

    items = [format_ticket_response(t, include_internal_notes=True) for t in tickets]
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

    return TicketListResponse(
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def get_ticket_details(
    db: AsyncSession,
    ctx: WorkspaceContext,
    ticket_id: str,
    include_internal_notes: bool = True,
) -> Ticket:
    stmt = (
        select(Ticket)
        .where(Ticket.id == ticket_id, Ticket.workspace_id == ctx.workspace_id)
        .options(
            joinedload(Ticket.customer),
            joinedload(Ticket.assigned_agent),
            selectinload(Ticket.messages).options(
                joinedload(TicketMessage.sender_user),
                joinedload(TicketMessage.sender_customer),
            ),
        )
    )
    result = await db.execute(stmt)
    ticket = result.unique().scalar_one_or_none()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found or does not belong to the active workspace.",
        )
    return ticket


async def list_ticket_messages(
    db: AsyncSession,
    ctx: WorkspaceContext,
    ticket_id: str,
    include_internal_notes: bool = True,
) -> List[MessageResponse]:
    ticket = await get_ticket_details(db, ctx, ticket_id)
    return [
        format_message_response(m)
        for m in ticket.messages
        if include_internal_notes or not m.is_internal_note
    ]


async def create_workspace_ticket(
    db: AsyncSession,
    ctx: WorkspaceContext,
    data: TicketCreate,
    customer_id: Optional[str] = None,
) -> Ticket:
    # 1. Resolve or create customer
    resolved_cust_id = customer_id
    if not resolved_cust_id:
        cust_email = (data.customer_email or "guest@customer.com").lower()
        cust_name = data.customer_name or "Guest Customer"

        c_res = await db.execute(
            select(Customer).where(Customer.workspace_id == ctx.workspace_id, Customer.email == cust_email)
        )
        existing_cust = c_res.scalar_one_or_none()
        if existing_cust:
            resolved_cust_id = existing_cust.id
        else:
            new_cust = Customer(
                workspace_id=ctx.workspace_id,
                email=cust_email,
                name=cust_name,
            )
            db.add(new_cust)
            await db.flush()
            resolved_cust_id = new_cust.id

    # 2. Get next ticket number for this workspace
    max_num_q = select(func.coalesce(func.max(Ticket.ticket_number), 1000)).where(
        Ticket.workspace_id == ctx.workspace_id
    )
    next_num = (await db.execute(max_num_q)).scalar_one() + 1

    ticket = Ticket(
        workspace_id=ctx.workspace_id,
        ticket_number=next_num,
        customer_id=resolved_cust_id,
        subject=data.subject,
        description=data.description,
        status="open",
        priority=data.priority,
        category=data.category,
    )
    db.add(ticket)
    await db.flush()

    # 3. Create initial customer message in thread
    initial_msg = TicketMessage(
        workspace_id=ctx.workspace_id,
        ticket_id=ticket.id,
        sender_type="customer",
        sender_customer_id=resolved_cust_id,
        body=data.description,
        is_internal_note=False,
        created_at=get_utc_now(),
    )
    db.add(initial_msg)

    # Advisory triage (classification + escalation flag). Provider failures never
    # block ticket creation; status changes remain a human decision.
    await apply_ai_triage(db, ctx.workspace_id, ticket)

    await db.commit()
    return await get_ticket_details(db, ctx, ticket.id)


async def update_ticket_status_priority(
    db: AsyncSession,
    ctx: WorkspaceContext,
    ticket_id: str,
    updates: TicketUpdate,
) -> TicketResponse:
    ticket = await get_ticket_details(db, ctx, ticket_id)

    if updates.status is not None:
        validate_status_transition(ticket.status, updates.status)
        ticket.status = updates.status
        if updates.status in ["resolved", "closed"] and not ticket.resolved_at:
            ticket.resolved_at = get_utc_now()
        elif updates.status not in ["resolved", "closed"]:
            ticket.resolved_at = None

    if updates.priority is not None:
        ticket.priority = updates.priority
    if updates.category is not None:
        ticket.category = updates.category

    ticket.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(ticket)
    return format_ticket_response(ticket, include_internal_notes=True)


async def add_ticket_message(
    db: AsyncSession,
    ctx: WorkspaceContext,
    ticket_id: str,
    body: str,
    sender_type: str,
    sender_user_id: Optional[str] = None,
    sender_customer_id: Optional[str] = None,
    is_internal_note: bool = False,
    metadata_json: Optional[str] = None,
) -> MessageResponse:
    ticket = await get_ticket_details(db, ctx, ticket_id)

    # Internal notes are a staff-only concept; never allow them from a customer context.
    if is_internal_note and sender_type != "agent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Internal notes can only be authored by support agents or admins.",
        )

    msg = TicketMessage(
        workspace_id=ctx.workspace_id,
        ticket_id=ticket.id,
        sender_type=sender_type,
        sender_user_id=sender_user_id,
        sender_customer_id=sender_customer_id,
        body=body,
        is_internal_note=is_internal_note,
        metadata_json=metadata_json,
        created_at=get_utc_now(),
    )
    db.add(msg)

    # Keep the lifecycle in sync with the conversation.
    if sender_type == "customer" and ticket.status == "waiting_for_customer":
        ticket.status = "in_progress"
    elif sender_type == "agent" and not is_internal_note and ticket.status in ["open", "in_progress"]:
        ticket.status = "waiting_for_customer"

    ticket.updated_at = get_utc_now()
    await db.commit()
    await db.refresh(msg)

    # Reload sender relations for the response payload
    if sender_user_id:
        user_res = await db.execute(select(User).where(User.id == sender_user_id))
        msg.sender_user = user_res.scalar_one_or_none()
    elif sender_customer_id:
        cust_res = await db.execute(select(Customer).where(Customer.id == sender_customer_id))
        msg.sender_customer = cust_res.scalar_one_or_none()

    return format_message_response(msg)


async def reclassify_ticket(
    db: AsyncSession,
    ctx: WorkspaceContext,
    ticket_id: str,
    *,
    apply_fields: bool = False,
) -> TicketResponse:
    """Re-runs AI triage on a ticket. Optionally applies the suggested category/priority."""
    ticket = await get_ticket_details(db, ctx, ticket_id)
    body_text = build_ticket_conversation(ticket)
    try:
        classification = await apply_ai_triage(
            db,
            ctx.workspace_id,
            ticket,
            body_text=body_text,
            apply_fields=apply_fields,
            raise_on_error=True,
        )
    except ProviderError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The AI provider is unavailable: {exc}",
        ) from exc

    if classification is None:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The AI provider is unavailable for triage right now.",
        )

    await db.commit()
    db.expire(ticket)
    return format_ticket_response(await get_ticket_details(db, ctx, ticket_id))


async def assign_ticket_agent(
    db: AsyncSession,
    ctx: WorkspaceContext,
    ticket_id: str,
    data: AssignTicketRequest,
) -> TicketResponse:
    ticket = await get_ticket_details(db, ctx, ticket_id)

    # Verify assignee is an admin/agent member of the active workspace.
    mem_q = select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == ctx.workspace_id,
        WorkspaceMembership.user_id == data.assigned_to_user_id,
        WorkspaceMembership.role.in_(["admin", "support_agent"]),
    )
    membership = (await db.execute(mem_q)).scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The target user is not a member of this workspace with a support agent or admin role.",
        )

    ticket.assigned_agent_id = data.assigned_to_user_id
    ticket.updated_at = get_utc_now()

    assignment = TicketAssignment(
        workspace_id=ctx.workspace_id,
        ticket_id=ticket.id,
        assigned_by_user_id=ctx.user_id,
        assigned_to_user_id=data.assigned_to_user_id,
        reason=data.reason,
        created_at=get_utc_now(),
    )
    db.add(assignment)
    await db.commit()

    # The ticket instance cached its previous assignee relationship; expire it so the
    # reloaded response reflects the new agent.
    db.expire(ticket)
    return await get_ticket_details(db, ctx, ticket_id)
