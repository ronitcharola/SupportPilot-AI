import secrets
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership, WorkspaceSettings
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceResponse,
    WorkspaceSettingsResponse,
    WorkspaceSettingsUpdate,
    AddMemberRequest,
    MembershipResponse,
)
from app.schemas.auth import WorkspaceMemberSummary
from app.dependencies import (
    get_current_user,
    get_workspace_context,
    require_admin,
    require_support_agent,
    WorkspaceContext,
    verify_csrf,
)
from app.services.auth_service import hash_password, get_user_memberships

router = APIRouter(prefix="/api/workspaces", tags=["Workspaces"])

@router.get("", response_model=List[WorkspaceMemberSummary])
async def list_user_workspaces(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists all active workspaces the current user belongs to."""
    return await get_user_memberships(db, user.id)

@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_csrf)])
async def create_workspace(
    data: WorkspaceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Creates a new workspace and assigns the caller as Admin."""
    base_slug = (data.slug or data.name).lower().replace(" ", "-")
    slug = "".join(c for c in base_slug if c.isalnum() or c == "-")
    if not slug:
        slug = f"ws-{secrets.token_hex(4)}"

    # Check collision
    existing = await db.execute(select(Workspace).where(Workspace.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{slug}-{secrets.token_hex(3)}"

    workspace = Workspace(name=data.name, slug=slug, is_active=True)
    db.add(workspace)
    await db.flush()

    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        user_id=user.id,
        role="admin",
    )
    db.add(membership)

    ws_settings = WorkspaceSettings(workspace_id=workspace.id)
    db.add(ws_settings)

    await db.commit()
    await db.refresh(workspace)
    return workspace

@router.get("/current/settings", response_model=WorkspaceSettingsResponse)
async def get_current_workspace_settings(
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Retrieves AI and operational settings for the active workspace."""
    result = await db.execute(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == ctx.workspace_id)
    )
    settings_obj = result.scalar_one_or_none()
    if not settings_obj:
        # Create default if missing
        settings_obj = WorkspaceSettings(workspace_id=ctx.workspace_id)
        db.add(settings_obj)
        await db.commit()
        await db.refresh(settings_obj)
    return settings_obj

@router.patch("/current/settings", response_model=WorkspaceSettingsResponse, dependencies=[Depends(verify_csrf)])
async def update_current_workspace_settings(
    updates: WorkspaceSettingsUpdate,
    ctx: WorkspaceContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Updates AI thresholds and provider configs for the workspace (Admin only)."""
    result = await db.execute(
        select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == ctx.workspace_id)
    )
    settings_obj = result.scalar_one_or_none()
    if not settings_obj:
        settings_obj = WorkspaceSettings(workspace_id=ctx.workspace_id)
        db.add(settings_obj)

    update_data = updates.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(settings_obj, field, val)

    await db.commit()
    await db.refresh(settings_obj)
    return settings_obj

@router.get("/current/members", response_model=List[MembershipResponse])
async def list_workspace_members(
    ctx: WorkspaceContext = Depends(require_support_agent),
    db: AsyncSession = Depends(get_db),
):
    """Lists all team members in the active workspace."""
    stmt = (
        select(WorkspaceMembership, User)
        .join(User, WorkspaceMembership.user_id == User.id)
        .where(WorkspaceMembership.workspace_id == ctx.workspace_id)
    )
    rows = (await db.execute(stmt)).all()
    members = []
    for mem, u in rows:
        members.append(
            MembershipResponse(
                id=mem.id,
                workspace_id=mem.workspace_id,
                user_id=u.id,
                role=mem.role,
                email=u.email,
                full_name=u.full_name,
            )
        )
    return members

@router.post("/current/members", response_model=MembershipResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_csrf)])
async def add_workspace_member(
    data: AddMemberRequest,
    ctx: WorkspaceContext = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Adds or invites a user to the workspace with specified role (Admin only)."""
    # Check if user already exists
    res = await db.execute(select(User).where(User.email == data.email.lower()))
    user = res.scalar_one_or_none()

    if not user:
        temp_pwd = data.temp_password or "PilotPass123!"
        user = User(
            email=data.email.lower(),
            password_hash=hash_password(temp_pwd),
            full_name=data.full_name or data.email.split("@")[0].title(),
            is_active=True,
        )
        db.add(user)
        await db.flush()

    # Check if membership already exists in this workspace
    existing_mem = await db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == ctx.workspace_id,
            WorkspaceMembership.user_id == user.id,
        )
    )
    if existing_mem.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this workspace.",
        )

    membership = WorkspaceMembership(
        workspace_id=ctx.workspace_id,
        user_id=user.id,
        role=data.role,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)

    return MembershipResponse(
        id=membership.id,
        workspace_id=ctx.workspace_id,
        user_id=user.id,
        role=membership.role,
        email=user.email,
        full_name=user.full_name,
    )
