from sqlalchemy import Column, String, Boolean, Text, DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import UUIDMixin, WorkspaceScopedMixin


class ActionProposal(Base, UUIDMixin, WorkspaceScopedMixin):
    """
    Represents a consequential action proposed by the AI that requires
    human approval before execution. The AI layer CANNOT execute these
    directly — only the human approval endpoint can.

    Status lifecycle: pending -> approved | rejected | expired
    """
    __tablename__ = "action_proposals"

    ticket_id = Column(String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    proposed_by_ai_provider = Column(String(100), nullable=False, default="mock")

    # Action type: 'issue_refund' | 'cancel_order' | 'flag_account' | 'apply_discount' | 'close_account'
    action_type = Column(String(100), nullable=False)

    # JSON-serialized action parameters (e.g. {"amount": 29.99, "reason": "..."})
    action_params_json = Column(Text, nullable=False)

    # Human-readable explanation for the agent reviewing this proposal
    rationale = Column(Text, nullable=False)
    ai_confidence = Column(Float, nullable=True)

    # Status: 'pending' | 'approved' | 'rejected' | 'executed' | 'expired'
    status = Column(String(50), default="pending", nullable=False, index=True)

    # Deterministic receipt produced by the mock action executor after approval.
    execution_result_json = Column(Text, nullable=True)

    # Decision tracking
    reviewed_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewer_note = Column(Text, nullable=True)

    # Execution tracking (idempotency)
    idempotency_key = Column(String(128), unique=True, nullable=True, index=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    ticket = relationship("Ticket")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])

    __table_args__ = (
        Index("ix_proposals_workspace_status", "workspace_id", "status"),
        Index("ix_proposals_ticket", "ticket_id"),
    )


class AuditLog(Base, UUIDMixin, WorkspaceScopedMixin):
    """
    Immutable audit trail for all security-relevant events:
    auth events, approvals, rejections, executions, settings changes.
    Rows are never updated or deleted.
    """
    __tablename__ = "audit_logs"

    # Event categories: 'auth' | 'ticket' | 'proposal' | 'workspace' | 'ai'
    event_category = Column(String(50), nullable=False, index=True)

    # Specific event type: 'login', 'logout', 'proposal_approved', 'proposal_rejected', etc.
    event_type = Column(String(100), nullable=False, index=True)

    actor_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_email = Column(String(255), nullable=True)  # denormalized for forensic immutability

    # Optional references
    target_ticket_id = Column(String(36), nullable=True, index=True)
    target_proposal_id = Column(String(36), nullable=True, index=True)

    # Full event payload (sanitized — no PII secrets)
    details_json = Column(Text, nullable=True)

    # Request metadata
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False)

    actor = relationship("User", foreign_keys=[actor_user_id])

    __table_args__ = (
        Index("ix_audit_workspace_created", "workspace_id", "created_at"),
        Index("ix_audit_event_type", "event_type"),
    )
