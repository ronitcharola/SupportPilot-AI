from sqlalchemy import Column, String, Boolean, Integer, Float, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin, WorkspaceScopedMixin

class Ticket(Base, UUIDMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "tickets"

    ticket_number = Column(Integer, nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    assigned_agent_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    subject = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    
    # Statuses: 'open', 'in_progress', 'pending_approval', 'waiting_for_customer', 'escalated', 'resolved', 'closed'
    status = Column(String(50), default="open", nullable=False, index=True)
    
    # Priorities: 'low', 'medium', 'high', 'urgent'
    priority = Column(String(50), default="medium", nullable=False, index=True)
    
    # Categories: 'billing', 'refunds', 'technical_issues', 'account_access', 'orders', 'shipping', 'product_questions', 'other'
    category = Column(String(50), nullable=True, index=True)

    # AI Metadata
    ai_intent = Column(String(100), nullable=True)
    ai_confidence = Column(Float, nullable=True)
    ai_sentiment = Column(String(50), nullable=True)
    ai_summary = Column(Text, nullable=True)
    ai_urgency_score = Column(Float, nullable=True)
    # Full classification payload (provider, model, suggested fields, reasons) for audit.
    ai_classification_json = Column(Text, nullable=True)
    is_escalated = Column(Boolean, default=False, nullable=False)
    escalation_reason = Column(Text, nullable=True)
    
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    workspace = relationship("Workspace")
    customer = relationship("Customer")
    assigned_agent = relationship("User", foreign_keys=[assigned_agent_id])
    messages = relationship("TicketMessage", back_populates="ticket", cascade="all, delete-orphan", order_by="TicketMessage.created_at.asc()")
    assignments = relationship("TicketAssignment", back_populates="ticket", cascade="all, delete-orphan", order_by="TicketAssignment.created_at.desc()")

    __table_args__ = (
        Index("ix_tickets_workspace_status", "workspace_id", "status"),
        Index("ix_tickets_workspace_priority", "workspace_id", "priority"),
        Index("ix_tickets_workspace_created", "workspace_id", "created_at"),
        Index("ix_tickets_workspace_escalated", "workspace_id", "is_escalated"),
    )

class TicketMessage(Base, UUIDMixin, WorkspaceScopedMixin):
    __tablename__ = "ticket_messages"

    ticket_id = Column(String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 'customer' | 'agent' | 'ai' | 'system'
    sender_type = Column(String(20), nullable=False)
    sender_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sender_customer_id = Column(String(36), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)

    body = Column(Text, nullable=False)
    is_internal_note = Column(Boolean, default=False, nullable=False)
    metadata_json = Column(Text, nullable=True)  # JSON-encoded citations, tokens, tool results
    created_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    ticket = relationship("Ticket", back_populates="messages")
    sender_user = relationship("User", foreign_keys=[sender_user_id])
    sender_customer = relationship("Customer", foreign_keys=[sender_customer_id])

class TicketAssignment(Base, UUIDMixin, WorkspaceScopedMixin):
    __tablename__ = "ticket_assignments"

    ticket_id = Column(String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_to_user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    ticket = relationship("Ticket", back_populates="assignments")
    assigned_by = relationship("User", foreign_keys=[assigned_by_user_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_user_id])
