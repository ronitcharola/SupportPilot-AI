"""Approval policy: strict action params and server-side role limits.

This module is pure validation. It cannot execute anything; it only decides whether a
human with a given role may approve an already-created proposal. See
`app/services/action_executor.py` for the mock executor and `app/ai/tools.py` for the
AI-side proposal boundary.
"""
from typing import Any, Dict, Literal, Optional

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import settings
from app.schemas.approval import ACTION_TYPES, ProposalPolicy


class RefundParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(gt=0, le=100_000)
    currency: Literal["USD"] = "USD"
    reason: str = Field(min_length=3, max_length=500)


class CancelOrderParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9#_\-]+$")
    reason: str = Field(min_length=3, max_length=500)


class DiscountParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    percent: float = Field(gt=0, le=100)
    duration_days: int = Field(default=30, ge=1, le=365)
    reason: str = Field(min_length=3, max_length=500)


class FlagAccountParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: Literal["low", "medium", "high"] = "medium"
    reason: str = Field(min_length=3, max_length=500)


PARAM_MODELS: Dict[str, type[BaseModel]] = {
    "issue_refund": RefundParams,
    "cancel_order": CancelOrderParams,
    "apply_discount": DiscountParams,
    "flag_account": FlagAccountParams,
}

ACTION_LABELS = {
    "issue_refund": "Issue refund",
    "cancel_order": "Cancel order",
    "apply_discount": "Apply discount",
    "flag_account": "Flag account",
}


def validate_action_params(action_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Validates and normalizes action params, rejecting unknown fields.

    Raises HTTP 422 with a readable detail so a malformed AI tool call can never
    reach execution with surprising parameters.
    """
    if action_type not in ACTION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown action type '{action_type}'. Allowed: {', '.join(ACTION_TYPES)}.",
        )
    model = PARAM_MODELS[action_type]
    try:
        validated = model(**params)
    except ValidationError as exc:
        messages = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'params'}: {error['msg']}"
            for error in exc.errors()
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid parameters for {action_type}: {messages}",
        ) from exc
    return validated.model_dump()


def approval_policy(action_type: str, params: Dict[str, Any]) -> ProposalPolicy:
    """Returns who may approve this proposal, based only on the stored parameters."""
    limit = settings.AGENT_APPROVAL_LIMIT_USD
    if action_type == "issue_refund":
        amount = float(params.get("amount", 0))
        return ProposalPolicy(
            requires_admin=amount > limit,
            agent_limit=limit,
            note=(
                f"Refunds above ${limit:,.2f} require an Admin."
                if amount > limit
                else f"Support agents may approve refunds up to ${limit:,.2f}."
            ),
        )
    if action_type == "apply_discount":
        percent = float(params.get("percent", 0))
        discount_limit = settings.AGENT_DISCOUNT_LIMIT_PERCENT
        return ProposalPolicy(
            requires_admin=percent > discount_limit,
            agent_limit=discount_limit,
            note=(
                f"Discounts above {discount_limit:g}% require an Admin."
                if percent > discount_limit
                else f"Support agents may approve discounts up to {discount_limit:g}%."
            ),
        )
    if action_type == "cancel_order":
        return ProposalPolicy(
            requires_admin=True,
            note="Order cancellations always require an Admin.",
        )
    return ProposalPolicy(
        requires_admin=False,
        note="Support agents and Admins may decide account flags.",
    )


def assert_role_can_decide(role: str, action_type: str, params: Dict[str, Any]) -> ProposalPolicy:
    """Server-side re-validation of approval permission.

    The frontend is never trusted: even if an agent can see the button, the endpoint
    refuses proposals that exceed their role's limits.
    """
    policy = approval_policy(action_type, params)
    if policy.requires_admin and role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Permission denied. {ACTION_LABELS.get(action_type, action_type)} requires an Admin "
                f"for this request. Ask a workspace Admin to review it."
            ),
        )
    return policy


def policy_summary(action_type: str, params: Dict[str, Any]) -> Optional[str]:
    return approval_policy(action_type, params).note
