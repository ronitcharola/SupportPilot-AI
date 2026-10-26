"""Append-only audit trail writer.

Callers own the transaction. Audit rows are never updated or deleted: there are no
service functions or API endpoints that mutate them, and details are sanitized before
storage so credentials/tokens cannot leak into the log.
"""
import json
import logging
from typing import Any, Dict, Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AuditLog
from app.models.base import get_utc_now
from app.models.user import User

logger = logging.getLogger(__name__)

FORBIDDEN_DETAIL_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "csrf_token",
    "secret",
    "api_key",
    "authorization",
}


def _sanitize_details(details: Optional[Dict[str, Any]]) -> Optional[str]:
    if not details:
        return None
    safe: Dict[str, Any] = {}
    for key, value in details.items():
        if key.lower() in FORBIDDEN_DETAIL_KEYS:
            safe[key] = "[redacted]"
        else:
            safe[key] = value
    try:
        payload = json.dumps(safe, default=str)
    except (TypeError, ValueError):
        payload = json.dumps({"note": "unserializable audit details"})
    return payload[:8000]


def _request_metadata(request: Optional[Request]) -> Dict[str, Optional[str]]:
    if request is None:
        return {"ip_address": None, "user_agent": None}
    client = getattr(request, "client", None)
    ip = client.host if client else None
    return {
        "ip_address": ip[:64] if ip else None,
        "user_agent": (request.headers.get("user-agent") or "")[:512] or None,
    }


async def record_audit_event(
    db: AsyncSession,
    *,
    workspace_id: str,
    event_category: str,
    event_type: str,
    actor: Optional[User] = None,
    actor_email: Optional[str] = None,
    ticket_id: Optional[str] = None,
    proposal_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> AuditLog:
    """Adds an audit row to the current transaction. The caller must commit."""
    metadata = _request_metadata(request)
    entry = AuditLog(
        workspace_id=workspace_id,
        event_category=event_category,
        event_type=event_type,
        actor_user_id=actor.id if actor else None,
        actor_email=(actor.email if actor else actor_email),
        target_ticket_id=ticket_id,
        target_proposal_id=proposal_id,
        details_json=_sanitize_details(details),
        ip_address=metadata["ip_address"],
        user_agent=metadata["user_agent"],
        created_at=get_utc_now(),
    )
    db.add(entry)
    logger.info(
        "audit workspace=%s category=%s event=%s actor=%s",
        workspace_id,
        event_category,
        event_type,
        entry.actor_email,
    )
    return entry
