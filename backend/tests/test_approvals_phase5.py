from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.ai import tools
from app.models.ai import ActionProposal, AuditLog
from app.models.base import get_utc_now
from app.models.ticket import Ticket
from sqlalchemy import select


async def _login(client: AsyncClient, email: str):
    res = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert res.status_code == 200, res.text
    return res


def _headers(login_res, workspace_id: str) -> dict:
    return {
        "X-Workspace-Id": workspace_id,
        "X-CSRF-Token": login_res.json()["csrf_token"],
    }


async def _create_ticket(client: AsyncClient, headers: dict, cookies, subject: str = "Refund request") -> dict:
    res = await client.post(
        "/api/tickets",
        headers=headers,
        cookies=cookies,
        json={
            "subject": subject,
            "description": "Customer was charged twice and wants the duplicate charge returned.",
            "customer_email": "charlie@customer.com",
            "customer_name": "Charlie Customer",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


async def _create_proposal(
    client: AsyncClient,
    headers: dict,
    cookies,
    ticket_id: str,
    amount: float = 120.0,
    action_type: str = "issue_refund",
    params: dict | None = None,
) -> dict:
    res = await client.post(
        f"/api/tickets/{ticket_id}/proposals",
        headers=headers,
        cookies=cookies,
        json={
            "action_type": action_type,
            "params": params
            or {"amount": amount, "currency": "USD", "reason": "Duplicate charge confirmed in ledger."},
            "rationale": "Verified two charges for the same invoice; policy allows a refund.",
            "ai_confidence": 0.92,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.asyncio
async def test_proposal_creation_is_pending_and_audited(client: AsyncClient, seeded_entities: dict):
    login = await _login(client, "admin@alpha.com")
    alpha = seeded_entities["ws_alpha"].id
    headers = _headers(login, alpha)
    ticket = await _create_ticket(client, headers, login.cookies)

    proposal = await _create_proposal(client, headers, login.cookies, ticket["id"], amount=120.0)
    assert proposal["status"] == "pending"
    assert proposal["params"]["amount"] == 120.0
    assert proposal["execution_result"] is None
    assert proposal["policy"]["requires_admin"] is False
    assert proposal["ticket_number"] == ticket["ticket_number"]

    ticket_res = await client.get(f"/api/tickets/{ticket['id']}", headers=headers, cookies=login.cookies)
    assert ticket_res.json()["status"] == "pending_approval"

    audit_res = await client.get(
        "/api/audit",
        headers=headers,
        cookies=login.cookies,
        params={"event_category": "proposal", "proposal_id": proposal["id"]},
    )
    assert audit_res.status_code == 200, audit_res.text
    events = [item["event_type"] for item in audit_res.json()["items"]]
    assert "proposal_created" in events
    created = next(item for item in audit_res.json()["items"] if item["event_type"] == "proposal_created")
    assert created["details"]["source"] == "api"
    assert created["actor_email"] == "admin@alpha.com"


@pytest.mark.asyncio
async def test_invalid_or_unknown_action_params_are_rejected(client: AsyncClient, seeded_entities: dict):
    login = await _login(client, "admin@alpha.com")
    headers = _headers(login, seeded_entities["ws_alpha"].id)
    ticket = await _create_ticket(client, headers, login.cookies)

    bad_amount = await client.post(
        f"/api/tickets/{ticket['id']}/proposals",
        headers=headers,
        cookies=login.cookies,
        json={
            "action_type": "issue_refund",
            "params": {"amount": -5, "currency": "USD", "reason": "Negative refund."},
            "rationale": "Test invalid amount handling.",
        },
    )
    assert bad_amount.status_code == 422

    unknown_field = await client.post(
        f"/api/tickets/{ticket['id']}/proposals",
        headers=headers,
        cookies=login.cookies,
        json={
            "action_type": "issue_refund",
            "params": {"amount": 10, "reason": "Extra field.", "admin_override": True},
            "rationale": "Attempt to smuggle an unknown field.",
        },
    )
    assert unknown_field.status_code == 422

    unknown_action = await client.post(
        f"/api/tickets/{ticket['id']}/proposals",
        headers=headers,
        cookies=login.cookies,
        json={
            "action_type": "delete_everything",
            "params": {},
            "rationale": "Attempt an unsupported action.",
        },
    )
    assert unknown_action.status_code == 422

    ticket_res = await client.get(f"/api/tickets/{ticket['id']}", headers=headers, cookies=login.cookies)
    assert ticket_res.json()["status"] == "open"


@pytest.mark.asyncio
async def test_agent_approval_is_atomic_and_idempotent(client: AsyncClient, seeded_entities: dict):
    login = await _login(client, "agent@alpha.com")
    alpha = seeded_entities["ws_alpha"].id
    headers = _headers(login, alpha)
    ticket = await _create_ticket(client, headers, login.cookies)
    proposal = await _create_proposal(client, headers, login.cookies, ticket["id"], amount=120.0)

    res = await client.post(
        f"/api/proposals/{proposal['id']}/approve",
        headers=headers,
        cookies=login.cookies,
        json={"idempotency_key": "agent-approve-key-0001", "note": "Verified in billing ledger."},
    )
    assert res.status_code == 200, res.text
    executed = res.json()
    assert executed["status"] == "executed"
    assert executed["execution_result"]["status"] == "refunded"
    assert executed["execution_result"]["amount"] == 120.0
    assert executed["reviewed_by_name"] == "Bob Alpha"
    assert executed["replayed"] is False

    ticket_res = await client.get(f"/api/tickets/{ticket['id']}", headers=headers, cookies=login.cookies)
    assert ticket_res.json()["status"] == "in_progress"

    replay = await client.post(
        f"/api/proposals/{proposal['id']}/approve",
        headers=headers,
        cookies=login.cookies,
        json={"idempotency_key": "agent-approve-key-0001"},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["replayed"] is True
    assert replay.json()["execution_result"] == executed["execution_result"]

    second_attempt = await client.post(
        f"/api/proposals/{proposal['id']}/approve",
        headers=headers,
        cookies=login.cookies,
        json={"idempotency_key": "agent-approve-key-0002"},
    )
    assert second_attempt.status_code == 409

    admin_login = await _login(client, "admin@alpha.com")
    audit_res = await client.get(
        "/api/audit",
        headers=_headers(admin_login, alpha),
        cookies=admin_login.cookies,
        params={"proposal_id": proposal["id"]},
    )
    assert audit_res.status_code == 200
    event_types = [item["event_type"] for item in audit_res.json()["items"]]
    assert "proposal_approved" in event_types
    assert "proposal_executed" in event_types
    assert event_types.count("proposal_executed") == 1


@pytest.mark.asyncio
async def test_agent_limit_is_enforced_server_side(client: AsyncClient, seeded_entities: dict):
    alpha = seeded_entities["ws_alpha"].id
    agent_login = await _login(client, "agent@alpha.com")
    agent_headers = _headers(agent_login, alpha)
    ticket = await _create_ticket(client, agent_headers, agent_login.cookies)
    proposal = await _create_proposal(client, agent_headers, agent_login.cookies, ticket["id"], amount=400.0)
    assert proposal["policy"]["requires_admin"] is True

    denied = await client.post(
        f"/api/proposals/{proposal['id']}/approve",
        headers=agent_headers,
        cookies=agent_login.cookies,
        json={"idempotency_key": "agent-over-limit-0001"},
    )
    assert denied.status_code == 403
    assert "admin" in denied.json()["detail"].lower()

    pending = await client.get(
        f"/api/proposals/{proposal['id']}", headers=agent_headers, cookies=agent_login.cookies
    )
    assert pending.json()["status"] == "pending"

    admin_login = await _login(client, "admin@alpha.com")
    admin_headers = _headers(admin_login, alpha)
    approved = await client.post(
        f"/api/proposals/{proposal['id']}/approve",
        headers=admin_headers,
        cookies=admin_login.cookies,
        json={"idempotency_key": "admin-over-limit-0001", "note": "Approved as supervisor."},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "executed"
    assert approved.json()["execution_result"]["amount"] == 400.0


@pytest.mark.asyncio
async def test_order_cancellation_always_needs_admin(client: AsyncClient, seeded_entities: dict):
    alpha = seeded_entities["ws_alpha"].id
    agent_login = await _login(client, "agent@alpha.com")
    agent_headers = _headers(agent_login, alpha)
    ticket = await _create_ticket(client, agent_headers, agent_login.cookies)
    proposal = await _create_proposal(
        client,
        agent_headers,
        agent_login.cookies,
        ticket["id"],
        action_type="cancel_order",
        params={"order_id": "ORD-4412", "reason": "Customer reports the package was lost."},
    )
    assert proposal["policy"]["requires_admin"] is True

    denied = await client.post(
        f"/api/proposals/{proposal['id']}/approve",
        headers=agent_headers,
        cookies=agent_login.cookies,
        json={"idempotency_key": "cancel-agent-key-0001"},
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_rejection_prevents_execution(client: AsyncClient, seeded_entities: dict):
    login = await _login(client, "agent@alpha.com")
    alpha = seeded_entities["ws_alpha"].id
    headers = _headers(login, alpha)
    ticket = await _create_ticket(client, headers, login.cookies)
    proposal = await _create_proposal(client, headers, login.cookies, ticket["id"], amount=80.0)

    res = await client.post(
        f"/api/proposals/{proposal['id']}/reject",
        headers=headers,
        cookies=login.cookies,
        json={"note": "Customer already received a service credit."},
    )
    assert res.status_code == 200, res.text
    rejected = res.json()
    assert rejected["status"] == "rejected"
    assert rejected["execution_result"] is None
    assert rejected["reviewer_note"] == "Customer already received a service credit."

    ticket_res = await client.get(f"/api/tickets/{ticket['id']}", headers=headers, cookies=login.cookies)
    assert ticket_res.json()["status"] == "in_progress"

    approve_after = await client.post(
        f"/api/proposals/{proposal['id']}/approve",
        headers=headers,
        cookies=login.cookies,
        json={"idempotency_key": "approve-after-reject-01"},
    )
    assert approve_after.status_code == 409


@pytest.mark.asyncio
async def test_expired_proposal_cannot_be_approved(
    client: AsyncClient, seeded_entities: dict, db_session
):
    login = await _login(client, "admin@alpha.com")
    alpha = seeded_entities["ws_alpha"].id
    headers = _headers(login, alpha)
    ticket = await _create_ticket(client, headers, login.cookies)
    proposal = await _create_proposal(client, headers, login.cookies, ticket["id"], amount=60.0)

    row = await db_session.execute(select(ActionProposal).where(ActionProposal.id == proposal["id"]))
    record = row.scalar_one()
    record.expires_at = get_utc_now() - timedelta(minutes=5)
    await db_session.commit()

    listing = await client.get(
        "/api/proposals", headers=headers, cookies=login.cookies, params={"status": "expired"}
    )
    assert listing.status_code == 200
    assert any(item["id"] == proposal["id"] for item in listing.json()["items"])
    assert listing.json()["status_counts"]["expired"] >= 1

    approve = await client.post(
        f"/api/proposals/{proposal['id']}/approve",
        headers=headers,
        cookies=login.cookies,
        json={"idempotency_key": "expired-approval-key-01"},
    )
    assert approve.status_code == 409
    assert "expired" in approve.json()["detail"].lower()

    audit = await client.get(
        "/api/audit",
        headers=headers,
        cookies=login.cookies,
        params={"proposal_id": proposal["id"], "event_type": "proposal_expired"},
    )
    assert audit.status_code == 200
    assert audit.json()["total"] >= 1


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_across_proposals_is_rejected(
    client: AsyncClient, seeded_entities: dict
):
    login = await _login(client, "admin@alpha.com")
    alpha = seeded_entities["ws_alpha"].id
    headers = _headers(login, alpha)
    ticket_one = await _create_ticket(client, headers, login.cookies, subject="First refund")
    ticket_two = await _create_ticket(client, headers, login.cookies, subject="Second refund")
    first = await _create_proposal(client, headers, login.cookies, ticket_one["id"], amount=25.0)
    second = await _create_proposal(client, headers, login.cookies, ticket_two["id"], amount=35.0)

    ok = await client.post(
        f"/api/proposals/{first['id']}/approve",
        headers=headers,
        cookies=login.cookies,
        json={"idempotency_key": "shared-key-abcdefgh"},
    )
    assert ok.status_code == 200

    reused = await client.post(
        f"/api/proposals/{second['id']}/approve",
        headers=headers,
        cookies=login.cookies,
        json={"idempotency_key": "shared-key-abcdefgh"},
    )
    assert reused.status_code == 409


@pytest.mark.asyncio
async def test_cross_workspace_proposals_are_invisible(client: AsyncClient, seeded_entities: dict):
    alpha_login = await _login(client, "admin@alpha.com")
    alpha_headers = _headers(alpha_login, seeded_entities["ws_alpha"].id)
    ticket = await _create_ticket(client, alpha_headers, alpha_login.cookies)
    proposal = await _create_proposal(client, alpha_headers, alpha_login.cookies, ticket["id"])

    beta_login = await _login(client, "admin@beta.com")
    beta_headers = _headers(beta_login, seeded_entities["ws_beta"].id)

    detail = await client.get(
        f"/api/proposals/{proposal['id']}", headers=beta_headers, cookies=beta_login.cookies
    )
    assert detail.status_code == 404

    approve = await client.post(
        f"/api/proposals/{proposal['id']}/approve",
        headers=beta_headers,
        cookies=beta_login.cookies,
        json={"idempotency_key": "beta-approval-key-0001"},
    )
    assert approve.status_code == 404

    beta_list = await client.get("/api/proposals", headers=beta_headers, cookies=beta_login.cookies)
    assert beta_list.status_code == 200
    assert beta_list.json()["total"] == 0


@pytest.mark.asyncio
async def test_authentication_and_admin_only_audit(client: AsyncClient, seeded_entities: dict):
    anonymous = await client.get("/api/proposals")
    assert anonymous.status_code == 401

    agent_login = await _login(client, "agent@alpha.com")
    agent_headers = _headers(agent_login, seeded_entities["ws_alpha"].id)
    forbidden = await client.get("/api/audit", headers=agent_headers, cookies=agent_login.cookies)
    assert forbidden.status_code == 403

    admin_login = await _login(client, "admin@alpha.com")
    admin_headers = _headers(admin_login, seeded_entities["ws_alpha"].id)
    audit = await client.get("/api/audit", headers=admin_headers, cookies=admin_login.cookies)
    assert audit.status_code == 200
    events = [item["event_type"] for item in audit.json()["items"]]
    assert "login_succeeded" in events

    # Append-only: the resource only exposes GET, so mutating verbs are rejected.
    assert (await client.delete("/api/audit", headers=admin_headers, cookies=admin_login.cookies)).status_code == 405
    assert (
        await client.patch("/api/audit", headers=admin_headers, cookies=admin_login.cookies, json={})
    ).status_code == 405


@pytest.mark.asyncio
async def test_closed_ticket_cannot_gain_a_proposal(client: AsyncClient, seeded_entities: dict):
    login = await _login(client, "admin@alpha.com")
    headers = _headers(login, seeded_entities["ws_alpha"].id)
    ticket = await _create_ticket(client, headers, login.cookies)

    closed = await client.patch(
        f"/api/tickets/{ticket['id']}",
        headers=headers,
        cookies=login.cookies,
        json={"status": "closed"},
    )
    assert closed.status_code == 200

    res = await client.post(
        f"/api/tickets/{ticket['id']}/proposals",
        headers=headers,
        cookies=login.cookies,
        json={
            "action_type": "issue_refund",
            "params": {"amount": 20, "currency": "USD", "reason": "Closed ticket refund."},
            "rationale": "Should be refused because the ticket is closed.",
        },
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_ai_tools_only_create_pending_proposals(
    client: AsyncClient, seeded_entities: dict, db_session
):
    login = await _login(client, "admin@alpha.com")
    alpha = seeded_entities["ws_alpha"].id
    headers = _headers(login, alpha)
    ticket = await _create_ticket(client, headers, login.cookies)

    proposal = await tools.propose_refund(
        db_session,
        workspace_id=alpha,
        ticket_id=ticket["id"],
        amount=95.5,
        reason="Duplicate charge verified by the ledger tool.",
        rationale="The AI proposes a refund; a human must approve it.",
        provider="mock",
        confidence=0.9,
    )
    assert proposal.status == "pending"
    assert proposal.executed_at is None
    assert proposal.reviewed_by_user_id is None
    assert proposal.idempotency_key is None

    # The AI package must not expose any execution capability.
    assert not hasattr(tools, "execute_approved_action")
    assert not hasattr(tools, "execute_action")

    ticket_row = await db_session.execute(select(Ticket).where(Ticket.id == ticket["id"]))
    assert ticket_row.scalar_one().status == "pending_approval"

    audit = await db_session.execute(
        select(AuditLog).where(
            AuditLog.target_proposal_id == proposal.id,
            AuditLog.event_type == "proposal_created",
        )
    )
    event = audit.scalar_one()
    assert event.actor_user_id is None
    assert '"source": "ai_tool"' in (event.details_json or "")
