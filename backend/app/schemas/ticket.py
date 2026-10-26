from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

# Canonical enums (kept in one place so API validation and services cannot drift)
TICKET_STATUS_PATTERN = "^(open|in_progress|pending_approval|waiting_for_customer|escalated|resolved|closed)$"
TICKET_PRIORITY_PATTERN = "^(low|medium|high|urgent)$"
TICKET_CATEGORY_PATTERN = "^(billing|refunds|technical_issues|account_access|orders|shipping|product_questions|other)$"


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=20_000)
    is_internal_note: bool = False


class MessageResponse(BaseModel):
    id: str
    ticket_id: str
    sender_type: str
    sender_name: str
    body: str
    is_internal_note: bool
    created_at: datetime
    metadata_json: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TicketCreate(BaseModel):
    subject: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=5, max_length=20_000)
    priority: str = Field(default="medium", pattern=TICKET_PRIORITY_PATTERN)
    category: Optional[str] = Field(default="product_questions", pattern=TICKET_CATEGORY_PATTERN)
    customer_email: Optional[str] = Field(default=None, max_length=255)
    customer_name: Optional[str] = Field(default=None, max_length=255)


class TicketUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern=TICKET_STATUS_PATTERN)
    priority: Optional[str] = Field(None, pattern=TICKET_PRIORITY_PATTERN)
    category: Optional[str] = Field(None, pattern=TICKET_CATEGORY_PATTERN)


class AssignTicketRequest(BaseModel):
    assigned_to_user_id: str
    reason: Optional[str] = Field(default=None, max_length=255)


class AssignmentResponse(BaseModel):
    id: str
    assigned_to_user_id: str
    assigned_to_name: Optional[str] = None
    assigned_by_user_id: Optional[str] = None
    assigned_by_name: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TicketResponse(BaseModel):
    id: str
    workspace_id: str
    ticket_number: int
    subject: str
    description: str
    status: str
    priority: str
    category: Optional[str] = None
    customer_id: str
    customer_name: str
    customer_email: str
    assigned_agent_id: Optional[str] = None
    assigned_agent_name: Optional[str] = None
    ai_intent: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_sentiment: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_urgency_score: Optional[float] = None
    ai_escalation_reasons: List[str] = []
    ai_suggested_category: Optional[str] = None
    ai_suggested_priority: Optional[str] = None
    is_escalated: bool = False
    escalation_reason: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # Statuses a reviewer is allowed to move this ticket to (server-enforced).
    allowed_transitions: List[str] = []
    messages: List[MessageResponse] = []

    model_config = ConfigDict(from_attributes=True)


class TicketListResponse(BaseModel):
    items: List[TicketResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
