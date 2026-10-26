"""Deterministic mock executor for approved consequential actions.

This module is only imported by the human approval service. The AI layer
(`app/ai/`) has no import path to it. In a production deployment this is where a
real billing/order provider would be called; here it returns a stable mock receipt
so the full approve → execute → audit trail can be demonstrated without side effects.
"""
from typing import Any, Dict
from uuid import uuid4

from app.models.ai import ActionProposal


def _reference(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def execute_approved_action(proposal: ActionProposal, params: Dict[str, Any]) -> Dict[str, Any]:
    """Executes an already-approved action and returns its receipt.

    Raises ValueError for an unknown action type so the caller can record a failed
    execution rather than silently marking the proposal as executed.
    """
    action_type = proposal.action_type
    base = {
        "provider": "mock",
        "mode": "demo",
        "proposal_id": proposal.id,
        "idempotency_key": proposal.idempotency_key,
    }

    if action_type == "issue_refund":
        return {
            **base,
            "status": "refunded",
            "reference": _reference("re"),
            "amount": round(float(params["amount"]), 2),
            "currency": params.get("currency", "USD"),
        }
    if action_type == "cancel_order":
        return {
            **base,
            "status": "cancelled",
            "reference": _reference("ord"),
            "order_id": params["order_id"],
        }
    if action_type == "apply_discount":
        return {
            **base,
            "status": "discount_applied",
            "reference": _reference("disc"),
            "percent": float(params["percent"]),
            "duration_days": int(params.get("duration_days", 30)),
        }
    if action_type == "flag_account":
        return {
            **base,
            "status": "account_flagged",
            "reference": _reference("flag"),
            "severity": params.get("severity", "medium"),
        }

    raise ValueError(f"Unsupported action type '{action_type}'.")
