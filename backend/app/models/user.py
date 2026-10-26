from sqlalchemy import Column, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.base import UUIDMixin, TimestampMixin, WorkspaceScopedMixin

class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    memberships = relationship("WorkspaceMembership", back_populates="user", cascade="all, delete-orphan")

class Customer(Base, UUIDMixin, TimestampMixin, WorkspaceScopedMixin):
    __tablename__ = "customers"

    email = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    external_reference = Column(String(100), nullable=True)

    __table_args__ = (
        UniqueConstraint("workspace_id", "email", name="uq_workspace_customer_email"),
    )

    workspace = relationship("Workspace", back_populates="customers")
