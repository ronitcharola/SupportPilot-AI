from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: Optional[str] = Field(None, max_length=100)

class WorkspaceResponse(BaseModel):
    id: str
    name: str
    slug: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class WorkspaceSettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    embedding_provider: Optional[str] = None
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    auto_escalate_urgency_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    proposal_expiry_hours: Optional[int] = Field(None, ge=1, le=168)

class WorkspaceSettingsResponse(BaseModel):
    workspace_id: str
    llm_provider: str
    llm_model: str
    embedding_provider: str
    embedding_dimension: int
    similarity_threshold: float
    auto_escalate_urgency_threshold: float
    proposal_expiry_hours: int

    model_config = ConfigDict(from_attributes=True)

class AddMemberRequest(BaseModel):
    email: str
    role: str = Field(..., pattern="^(admin|support_agent)$")
    full_name: Optional[str] = None
    temp_password: Optional[str] = None

class MembershipResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    role: str
    email: str
    full_name: str

    model_config = ConfigDict(from_attributes=True)
