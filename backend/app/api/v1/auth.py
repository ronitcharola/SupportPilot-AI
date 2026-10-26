from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    AuthResponse,
    WorkspaceMemberSummary,
)
from app.services.auth_service import (
    register_admin_user,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_csrf_token,
    set_auth_cookies,
    clear_auth_cookies,
    get_user_memberships,
)
from app.services.audit_service import record_audit_event
from app.dependencies import get_current_user, get_workspace_context, WorkspaceContext


async def _first_workspace_id(db: AsyncSession, user_id: str) -> str | None:
    result = await db.execute(
        select(WorkspaceMembership.workspace_id)
        .where(WorkspaceMembership.user_id == user_id)
        .order_by(WorkspaceMembership.created_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegister,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Registers an initial administrator user and provisions their first workspace."""
    user, workspace, access_token, csrf_token = await register_admin_user(db, data)
    set_auth_cookies(response, access_token, csrf_token)

    await record_audit_event(
        db,
        workspace_id=workspace.id,
        event_category="auth",
        event_type="user_registered",
        actor=user,
        details={"workspace_slug": workspace.slug, "role": "admin"},
        request=request,
    )
    await db.commit()

    memberships = await get_user_memberships(db, user.id)
    active_ws = next((m for m in memberships if m.workspace_id == workspace.id), None)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        active_workspace=active_ws,
        memberships=memberships,
        csrf_token=csrf_token,
        message="Registration successful.",
    )

@router.post("/login", response_model=AuthResponse)
async def login(
    data: UserLogin,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticates with email and password, setting secure httpOnly session cookies."""
    result = await db.execute(select(User).where(User.email == data.email.lower()))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        # Audit failed attempts for known accounts without revealing whether the
        # email exists in the HTTP response.
        if user:
            workspace_id = await _first_workspace_id(db, user.id)
            if workspace_id:
                await record_audit_event(
                    db,
                    workspace_id=workspace_id,
                    event_category="auth",
                    event_type="login_failed",
                    actor_email=user.email,
                    details={"reason": "invalid_password"},
                    request=request,
                )
                await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        workspace_id = await _first_workspace_id(db, user.id)
        if workspace_id:
            await record_audit_event(
                db,
                workspace_id=workspace_id,
                event_category="auth",
                event_type="login_failed",
                actor_email=user.email,
                details={"reason": "account_deactivated"},
                request=request,
            )
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    memberships = await get_user_memberships(db, user.id)
    first_ws_id = memberships[0].workspace_id if memberships else None

    if first_ws_id:
        await record_audit_event(
            db,
            workspace_id=first_ws_id,
            event_category="auth",
            event_type="login_succeeded",
            actor=user,
            details={"workspace_slug": memberships[0].workspace_slug},
            request=request,
        )
        await db.commit()

    access_token = create_access_token({"sub": user.id, "email": user.email, "workspace_id": first_ws_id})
    csrf_token = generate_csrf_token()
    set_auth_cookies(response, access_token, csrf_token)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        active_workspace=memberships[0] if memberships else None,
        memberships=memberships,
        csrf_token=csrf_token,
        message="Login successful.",
    )

@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Terminates session by clearing auth and CSRF cookies."""
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
    payload = decode_access_token(token) if token else None
    if payload and payload.get("sub"):
        user = (
            await db.execute(select(User).where(User.id == payload["sub"]))
        ).scalar_one_or_none()
        workspace_id = await _first_workspace_id(db, payload["sub"])
        if user and workspace_id:
            await record_audit_event(
                db,
                workspace_id=workspace_id,
                event_category="auth",
                event_type="logged_out",
                actor=user,
                request=request,
            )
            await db.commit()

    clear_auth_cookies(response)
    return {"message": "Logged out successfully."}

@router.get("/me", response_model=AuthResponse)
async def get_me(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns profile and memberships for the currently authenticated user."""
    memberships = await get_user_memberships(db, user.id)
    
    # Try resolving active workspace
    active_ws_id = request.headers.get("X-Workspace-Id") or (memberships[0].workspace_id if memberships else None)
    active_ws = next((m for m in memberships if m.workspace_id == active_ws_id), memberships[0] if memberships else None)

    # Refresh CSRF token if missing
    csrf_token = request.cookies.get("csrf_token")
    if not csrf_token:
        csrf_token = generate_csrf_token()
        token = request.cookies.get("access_token")
        if token:
            set_auth_cookies(response, token, csrf_token)

    return AuthResponse(
        user=UserResponse.model_validate(user),
        active_workspace=active_ws,
        memberships=memberships,
        csrf_token=csrf_token,
        message="Session active.",
    )
