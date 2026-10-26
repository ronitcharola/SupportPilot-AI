from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="Minimum 8 characters")
    full_name: str = Field(min_length=2)
    workspace_name: str = Field(min_length=2, description="Name for the initial workspace")

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class WorkspaceMemberSummary(BaseModel):
    workspace_id: str
    workspace_name: str
    workspace_slug: str
    role: str

class AuthResponse(BaseModel):
    user: UserResponse
    active_workspace: Optional[WorkspaceMemberSummary] = None
    memberships: List[WorkspaceMemberSummary] = []
    csrf_token: str
    message: str = "Authenticated successfully"
