import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Response, HTTPException, status

from app.config import settings
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership, WorkspaceSettings
from app.schemas.auth import UserRegister, WorkspaceMemberSummary

ph = PasswordHasher()

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    try:
        return ph.verify(hashed, password)
    except (VerifyMismatchError, VerificationError):
        return False

def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

def set_auth_cookies(response: Response, token: str, csrf_token: str):
    is_secure = settings.ENVIRONMENT == "production"
    # Set JWT in httpOnly SameSite cookie
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    # Set CSRF token in readable cookie for double-submit header validation
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        secure=is_secure,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

def clear_auth_cookies(response: Response):
    response.delete_cookie(key=settings.AUTH_COOKIE_NAME, path="/")
    response.delete_cookie(key=settings.CSRF_COOKIE_NAME, path="/")

async def register_admin_user(
    db: AsyncSession,
    register_data: UserRegister,
) -> Tuple[User, Workspace, str, str]:
    """Registers a new user, creates their initial workspace, and grants the Admin role."""
    # Check if user already exists
    existing = await db.execute(select(User).where(User.email == register_data.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # Create User
    user = User(
        email=register_data.email.lower(),
        password_hash=hash_password(register_data.password),
        full_name=register_data.full_name,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # Generate workspace slug
    base_slug = register_data.workspace_name.lower().replace(" ", "-")
    slug = "".join(c for c in base_slug if c.isalnum() or c == "-")
    if not slug:
        slug = f"workspace-{secrets.token_hex(4)}"
    
    # Check slug collision
    slug_check = await db.execute(select(Workspace).where(Workspace.slug == slug))
    if slug_check.scalar_one_or_none():
        slug = f"{slug}-{secrets.token_hex(3)}"

    workspace = Workspace(
        name=register_data.workspace_name,
        slug=slug,
        is_active=True,
    )
    db.add(workspace)
    await db.flush()

    # Add Admin Membership
    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        user_id=user.id,
        role="admin",
    )
    db.add(membership)

    # Initialize Workspace Settings
    ws_settings = WorkspaceSettings(
        workspace_id=workspace.id,
        llm_provider=settings.LLM_PROVIDER,
        llm_model=settings.LLM_MODEL,
        embedding_provider=settings.EMBEDDING_PROVIDER,
        embedding_dimension=settings.EMBEDDING_DIMENSION,
        similarity_threshold=settings.SIMILARITY_THRESHOLD,
    )
    db.add(ws_settings)

    await db.commit()
    await db.refresh(user)
    await db.refresh(workspace)

    # Generate tokens
    access_token = create_access_token({"sub": user.id, "email": user.email, "workspace_id": workspace.id})
    csrf_token = generate_csrf_token()

    return user, workspace, access_token, csrf_token

async def get_user_memberships(db: AsyncSession, user_id: str) -> List[WorkspaceMemberSummary]:
    stmt = (
        select(WorkspaceMembership, Workspace)
        .join(Workspace, WorkspaceMembership.workspace_id == Workspace.id)
        .where(WorkspaceMembership.user_id == user_id, Workspace.is_active == True)
    )
    result = await db.execute(stmt)
    rows = result.all()
    summaries = []
    for mem, ws in rows:
        summaries.append(
            WorkspaceMemberSummary(
                workspace_id=ws.id,
                workspace_name=ws.name,
                workspace_slug=ws.slug,
                role=mem.role,
            )
        )
    return summaries
