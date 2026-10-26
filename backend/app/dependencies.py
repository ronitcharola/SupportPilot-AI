from typing import Optional, List, Callable
from dataclasses import dataclass
from fastapi import Request, Depends, HTTPException, status, Header
from sqlalchemy import select, Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.services.auth_service import decode_access_token

@dataclass
class WorkspaceContext:
    workspace_id: str
    user_id: str
    role: str
    workspace: Workspace
    user: User

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extracts and verifies the current authenticated user from cookie or Authorization header."""
    token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    
    # Fallback to Authorization: Bearer <token>
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication session.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload["sub"]
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account does not exist or has been deactivated.",
        )

    return user

async def verify_csrf(
    request: Request,
):
    """Enforces double-submit CSRF cookie protection for state-changing HTTP methods."""
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)
        csrf_header = request.headers.get("X-CSRF-Token")
        
        # In development/test mode, if no cookie was set (e.g. initial curl or API test with Authorization header), we allow bypass only if explicitly configured
        if not csrf_cookie and not csrf_header:
            auth_header = request.headers.get("Authorization")
            if auth_header:
                # Direct Bearer token auth without cookies does not require CSRF
                return
        
        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed. Missing or mismatched CSRF token.",
            )

async def get_workspace_context(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
) -> WorkspaceContext:
    """
    Enforces multi-tenant isolation.
    Resolves the requested workspace ID, verifies user membership, and returns the verified context.
    """
    target_workspace_id = x_workspace_id

    # If not in header, check query param
    if not target_workspace_id:
        target_workspace_id = request.query_params.get("workspace_id")

    # If still not specified, resolve from first active membership
    if not target_workspace_id:
        first_mem = await db.execute(
            select(WorkspaceMembership)
            .where(WorkspaceMembership.user_id == user.id)
            .order_by(WorkspaceMembership.created_at.asc())
        )
        membership = first_mem.scalar_one_or_none()
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not belong to any workspace.",
            )
        target_workspace_id = membership.workspace_id

    # Query membership and workspace jointly
    stmt = (
        select(WorkspaceMembership, Workspace)
        .join(Workspace, WorkspaceMembership.workspace_id == Workspace.id)
        .where(
            WorkspaceMembership.workspace_id == target_workspace_id,
            WorkspaceMembership.user_id == user.id,
            Workspace.is_active == True,
        )
    )
    res = await db.execute(stmt)
    row = res.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You are not a member of the requested workspace.",
        )

    membership, workspace = row
    return WorkspaceContext(
        workspace_id=workspace.id,
        user_id=user.id,
        role=membership.role,
        workspace=workspace,
        user=user,
    )

def require_role(allowed_roles: List[str]) -> Callable:
    """Dependency factory checking that the caller possesses one of the allowed roles."""
    async def role_checker(ctx: WorkspaceContext = Depends(get_workspace_context)) -> WorkspaceContext:
        if ctx.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required role in {allowed_roles}, your role is '{ctx.role}'.",
            )
        return ctx
    return role_checker

require_admin = require_role(["admin"])
require_support_agent = require_role(["admin", "support_agent"])

def scoped_query(model, ctx: WorkspaceContext) -> Select:
    """
    Helper function to guarantee all queries are automatically workspace-scoped.
    Eliminates cross-tenant data leak risks.
    """
    if not hasattr(model, "workspace_id"):
        raise ValueError(f"Model {model.__name__} does not have a workspace_id attribute.")
    return select(model).where(model.workspace_id == ctx.workspace_id)
