from sqlalchemy import Column, String, Boolean, Integer, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin, generate_uuid

class Workspace(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workspaces"

    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    memberships = relationship("WorkspaceMembership", back_populates="workspace", cascade="all, delete-orphan")
    settings = relationship("WorkspaceSettings", back_populates="workspace", uselist=False, cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="workspace", cascade="all, delete-orphan")

class WorkspaceMembership(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workspace_memberships"

    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # 'admin' | 'support_agent'

    # Constraints
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="memberships")
    user = relationship("User", back_populates="memberships")

class WorkspaceSettings(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "workspace_settings"

    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    llm_provider = Column(String(50), default="mock", nullable=False)
    llm_model = Column(String(100), default="mock-gpt-4o", nullable=False)
    embedding_provider = Column(String(50), default="mock", nullable=False)
    embedding_dimension = Column(Integer, default=1536, nullable=False)
    similarity_threshold = Column(Float, default=0.72, nullable=False)
    auto_escalate_urgency_threshold = Column(Float, default=0.85, nullable=False)
    proposal_expiry_hours = Column(Integer, default=24, nullable=False)

    # Relationships
    workspace = relationship("Workspace", back_populates="settings")
