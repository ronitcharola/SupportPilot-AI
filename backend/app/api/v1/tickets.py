from typing import List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.ticket import (
    TicketCreate,
    TicketUpdate,
    TicketResponse,
    TicketListResponse,
    MessageCreate,
    MessageResponse,
    AssignTicketRequest,
)
from app.ai.base import ProviderError
from app.dependencies import (
    get_workspace_context,
    require_support_agent,
    WorkspaceContext,
    verify_csrf,
)
from app.schemas.triage import SuggestedReplyResponse
from app.schemas.approval import ProposalCreate, ProposalResponse
from app.services.approval_service import create_ticket_proposal
from app.services.ticket_service import (
    list_workspace_tickets,
    get_ticket_details,
    list_ticket_messages,
    create_workspace_ticket,
    update_ticket_status_priority,
    add_ticket_message,
    assign_ticket_agent,
    reclassify_ticket,
    format_ticket_response,
)
from app.services.triage_service import suggest_ticket_reply

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])

@router.get("", response_model=TicketListResponse)
async def list_tickets(
    status: Optional[str] = Query(None, description="Filter by ticket status"),
    priority: Optional[str] = Query(None, description="Filter by ticket priority"),
    category: Optional[str] = Query(None, description="Filter by ticket category"),
    assignee_id: Optional[str] = Query(None, description="Filter by assigned agent user id"),
    unassigned: bool = Query(False, description="Only tickets without an assignee"),
    search: Optional[str] = Query(None, max_length=200, description="Search subject, body, customer name and email"),
    assigned_to_me: bool = Query(False, description="Filter to tickets assigned to caller"),
    escalated: bool = Query(False, description="Only tickets flagged for human escalation"),
    sort_by: Literal["created_at", "updated_at", "ticket_number", "priority", "status", "subject"] = Query(
        "created_at", description="Sort field"
    ),
    sort_order: Literal["asc", "desc"] = Query("desc", description="Sort direction"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Lists workspace-scoped tickets with filtering, search, sorting and pagination."""
    return await list_workspace_tickets(
        db=db,
        ctx=ctx,
        status_filter=status,
        priority_filter=priority,
        category_filter=category,
        assignee_id=assignee_id,
        unassigned=unassigned,
        assigned_to_me=assigned_to_me,
        escalated=escalated,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )

@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_csrf)])
async def create_ticket(
    data: TicketCreate,
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Creates a new ticket within the active workspace."""
    ticket = await create_workspace_ticket(db, ctx, data)
    return format_ticket_response(ticket, include_internal_notes=True)

@router.get("/{id}", response_model=TicketResponse)
async def get_ticket(
    id: str,
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves full ticket conversation thread, customer details, and internal notes."""
    ticket = await get_ticket_details(db, ctx, id)
    return format_ticket_response(ticket, include_internal_notes=True)

@router.patch("/{id}", response_model=TicketResponse, dependencies=[Depends(verify_csrf)])
async def update_ticket(
    id: str,
    updates: TicketUpdate,
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Updates ticket status, priority, or category. Status changes are lifecycle-validated."""
    return await update_ticket_status_priority(db, ctx, id, updates)

@router.get("/{id}/messages", response_model=List[MessageResponse])
async def get_ticket_messages(
    id: str,
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Lists the full conversation thread, including internal notes (staff only)."""
    return await list_ticket_messages(db, ctx, id, include_internal_notes=True)

@router.post("/{id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_csrf)])
async def post_ticket_message(
    id: str,
    data: MessageCreate,
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Appends an agent response or an internal note to the ticket conversation."""
    return await add_ticket_message(
        db=db,
        ctx=ctx,
        ticket_id=id,
        body=data.body,
        sender_type="agent",
        sender_user_id=ctx.user_id,
        is_internal_note=data.is_internal_note,
    )

@router.post(
    "/{id}/proposals",
    response_model=ProposalResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
async def propose_action(
    id: str,
    data: ProposalCreate,
    request: Request,
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Creates a pending consequential-action proposal for human approval.

    This endpoint can only create a `pending` proposal; it never executes anything.
    The AI layer uses the same service through `app/ai/tools.py`.
    """
    return await create_ticket_proposal(db, ctx, id, data, request)


@router.post(
    "/{id}/classify",
    response_model=TicketResponse,
    dependencies=[Depends(verify_csrf)],
)
async def classify_ticket_endpoint(
    id: str,
    apply: bool = Query(False, description="Apply the suggested category and priority"),
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Re-runs AI triage; optionally applies the suggested category/priority (staff only)."""
    return await reclassify_ticket(db, ctx, id, apply_fields=apply)


@router.post("/{id}/suggested-reply", response_model=SuggestedReplyResponse)
async def suggested_reply(
    id: str,
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Drafts a knowledge-grounded reply for agent review. Nothing is sent or saved."""
    ticket = await get_ticket_details(db, ctx, id)
    try:
        return await suggest_ticket_reply(
            db,
            workspace_id=ctx.workspace_id,
            workspace_name=ctx.workspace.name,
            ticket=ticket,
        )
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The AI provider is unavailable: {exc}",
        ) from exc


@router.post("/{id}/assign", response_model=TicketResponse, dependencies=[Depends(verify_csrf)])
async def assign_ticket(
    id: str,
    data: AssignTicketRequest,
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Assigns or reassigns the ticket to an agent within the workspace."""
    ticket = await assign_ticket_agent(db, ctx, id, data)
    return format_ticket_response(ticket, include_internal_notes=True)
