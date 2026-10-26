from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

ACTION_TYPES = ["issue_refund", "cancel_order", "apply_discount", "flag_account"]
PROPOSAL_STATUSES = ["pending", "approved", "rejected", "executed", "expired"]

ActionType = Literal["issue_refund", "cancel_order", "apply_discount", "flag_account"]
ProposalStatus = Literal["pending", "approved", "rejected", "executed", "expired"]


class ProposalCreate(BaseModel):
    """A consequential action request. Creation can only ever produce a pending proposal."""

    action_type: ActionType
    params: Dict[str, Any]
    rationale: str = Field(min_length=5, max_length=2000)
    ai_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ApprovalDecision(BaseModel):
    """Human decision on a pending proposal.

    The idempotency key makes an approval safely retryable: replaying the same key
    returns the original execution instead of acting twice.
    """

    idempotency_key: str = Field(min_length=8, max_length=128)
    note: Optional[str] = Field(default=None, max_length=2000)


class RejectionDecision(BaseModel):
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=128)
    note: Optional[str] = Field(default=None, max_length=2000)


class ProposalPolicy(BaseModel):
    """Server-computed policy view so the UI can explain who may approve."""

    requires_admin: bool
    note: Optional[str] = None
    agent_limit: Optional[float] = None


class ProposalResponse(BaseModel):
    id: str
    workspace_id: str
    ticket_id: str
    ticket_number: Optional[int] = None
    ticket_subject: Optional[str] = None
    action_type: str
    params: Dict[str, Any]
    rationale: str
    ai_confidence: Optional[float] = None
    proposed_by_ai_provider: str
    status: str
    policy: ProposalPolicy
    reviewed_by_user_id: Optional[str] = None
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[str] = None
    reviewer_note: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    executed_at: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: str
    replayed: bool = False


class ProposalListResponse(BaseModel):
    items: List[ProposalResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    status_counts: Dict[str, int] = {}


class AuditLogResponse(BaseModel):
    id: str
    event_category: str
    event_type: str
    actor_user_id: Optional[str] = None
    actor_email: Optional[str] = None
    target_ticket_id: Optional[str] = None
    target_proposal_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: str


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
