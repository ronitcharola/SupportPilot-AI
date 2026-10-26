from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Header
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.ticket import Ticket, TicketMessage
from app.models.user import Customer
from app.models.workspace import Workspace
from app.schemas.ticket import TicketCreate, TicketResponse, MessageCreate, MessageResponse
from app.services.ticket_service import (
    format_ticket_response,
    format_message_response,
    get_utc_now,
)
from app.services.triage_service import apply_ai_triage

router = APIRouter(prefix="/api/portal", tags=["Customer Portal"])

async def get_portal_workspace(
    db: AsyncSession,
    workspace_slug: Optional[str] = None,
    x_workspace_slug: Optional[str] = Header(None, alias="X-Workspace-Slug"),
) -> Workspace:
    slug = workspace_slug or x_workspace_slug or "acme-corp"
    res = await db.execute(select(Workspace).where(Workspace.slug == slug, Workspace.is_active == True))
    ws = res.scalar_one_or_none()
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{slug}' not found.",
        )
    return ws

@router.get("/tickets", response_model=List[TicketResponse])
async def list_customer_tickets(
    email: str = Query(..., description="Customer email address"),
    workspace_slug: Optional[str] = Query("acme-corp"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves tickets created by this customer (internal notes excluded)."""
    ws = await get_portal_workspace(db, workspace_slug)
    
    # Resolve customer
    cust_res = await db.execute(
        select(Customer).where(Customer.workspace_id == ws.id, Customer.email == email.lower())
    )
    customer = cust_res.scalar_one_or_none()
    if not customer:
        return []

    stmt = (
        select(Ticket)
        .where(Ticket.workspace_id == ws.id, Ticket.customer_id == customer.id)
        .options(
            joinedload(Ticket.customer),
            joinedload(Ticket.assigned_agent),
            selectinload(Ticket.messages).options(
                joinedload(TicketMessage.sender_user),
                joinedload(TicketMessage.sender_customer),
            ),
        )
        .order_by(desc(Ticket.created_at))
    )
    results = (await db.execute(stmt)).unique().scalars().all()
    # Internal notes and internal AI triage metadata are strictly stripped.
    return [
        format_ticket_response(t, include_internal_notes=False, include_ai_metadata=False)
        for t in results
    ]

@router.post("/tickets", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_portal_ticket(
    data: TicketCreate,
    workspace_slug: Optional[str] = Query("acme-corp"),
    db: AsyncSession = Depends(get_db),
):
    """Submits a new customer support ticket through the customer portal."""
    ws = await get_portal_workspace(db, workspace_slug)
    cust_email = (data.customer_email or "guest@customer.com").lower()
    cust_name = data.customer_name or "Guest Customer"

    # Find or create customer
    c_res = await db.execute(
        select(Customer).where(Customer.workspace_id == ws.id, Customer.email == cust_email)
    )
    customer = c_res.scalar_one_or_none()
    if not customer:
        customer = Customer(
            workspace_id=ws.id,
            email=cust_email,
            name=cust_name,
        )
        db.add(customer)
        await db.flush()

    # Get next ticket number
    max_num_q = select(Ticket.ticket_number).where(Ticket.workspace_id == ws.id).order_by(desc(Ticket.ticket_number)).limit(1)
    last_num = (await db.execute(max_num_q)).scalar_one_or_none() or 1000
    next_num = last_num + 1

    ticket = Ticket(
        workspace_id=ws.id,
        ticket_number=next_num,
        customer_id=customer.id,
        subject=data.subject,
        description=data.description,
        status="open",
        priority=data.priority,
        category=data.category or "product_questions",
    )
    db.add(ticket)
    await db.flush()

    # Initial message
    msg = TicketMessage(
        workspace_id=ws.id,
        ticket_id=ticket.id,
        sender_type="customer",
        sender_customer_id=customer.id,
        body=data.description,
        is_internal_note=False,
        created_at=get_utc_now(),
    )
    db.add(msg)

    # Advisory classification; customers never see the internal triage metadata.
    await apply_ai_triage(db, ws.id, ticket)

    await db.commit()

    # Reload with relationships
    stmt = (
        select(Ticket)
        .where(Ticket.id == ticket.id)
        .options(
            joinedload(Ticket.customer),
            joinedload(Ticket.assigned_agent),
            selectinload(Ticket.messages).options(
                joinedload(TicketMessage.sender_user),
                joinedload(TicketMessage.sender_customer),
            ),
        )
    )
    loaded = (await db.execute(stmt)).unique().scalar_one()
    return format_ticket_response(loaded, include_internal_notes=False, include_ai_metadata=False)

@router.get("/tickets/{id}", response_model=TicketResponse)
async def get_portal_ticket(
    id: str,
    email: str = Query(..., description="Customer email for verification"),
    workspace_slug: Optional[str] = Query("acme-corp"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves single customer ticket. Guarantees internal notes are scrubbed."""
    ws = await get_portal_workspace(db, workspace_slug)
    stmt = (
        select(Ticket)
        .where(Ticket.id == id, Ticket.workspace_id == ws.id)
        .options(
            joinedload(Ticket.customer),
            joinedload(Ticket.assigned_agent),
            selectinload(Ticket.messages).options(
                joinedload(TicketMessage.sender_user),
                joinedload(TicketMessage.sender_customer),
            ),
        )
    )
    ticket = (await db.execute(stmt)).unique().scalar_one_or_none()
    if not ticket or not ticket.customer or ticket.customer.email.lower() != email.lower():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found or does not belong to this customer.",
        )

    # Return without internal notes or internal AI triage metadata.
    return format_ticket_response(ticket, include_internal_notes=False, include_ai_metadata=False)

@router.post("/tickets/{id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def customer_reply_ticket(
    id: str,
    data: MessageCreate,
    email: str = Query(..., description="Customer email for verification"),
    workspace_slug: Optional[str] = Query("acme-corp"),
    db: AsyncSession = Depends(get_db),
):
    """Appends a customer response to the ticket conversation."""
    ws = await get_portal_workspace(db, workspace_slug)
    stmt = (
        select(Ticket)
        .where(Ticket.id == id, Ticket.workspace_id == ws.id)
        .options(joinedload(Ticket.customer))
    )
    ticket = (await db.execute(stmt)).scalar_one_or_none()
    if not ticket or not ticket.customer or ticket.customer.email.lower() != email.lower():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found or customer mismatch.",
        )

    msg = TicketMessage(
        workspace_id=ws.id,
        ticket_id=ticket.id,
        sender_type="customer",
        sender_customer_id=ticket.customer.id,
        body=data.body,
        is_internal_note=False,
        created_at=get_utc_now(),
    )
    db.add(msg)

    # Customer replies always move an idle/resolved ticket back into active triage.
    if ticket.status == "waiting_for_customer":
        ticket.status = "in_progress"
    elif ticket.status in ["resolved", "closed"]:
        ticket.status = "open"
        ticket.resolved_at = None
    ticket.updated_at = get_utc_now()

    await db.commit()
    await db.refresh(msg)
    msg.sender_customer = ticket.customer

    return format_message_response(msg)
