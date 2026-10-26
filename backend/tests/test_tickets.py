import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_ticket_lifecycle_and_internal_notes(client: AsyncClient, seeded_entities: dict):
    """
    Tests ticket creation, agent responses, internal notes, and status updates.
    """
    # 1. Login as Alice Admin
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "admin@alpha.com", "password": "Password123!"},
    )
    assert login_res.status_code == 200
    cookies = login_res.cookies
    csrf_token = login_res.json()["csrf_token"]
    alpha_id = seeded_entities["ws_alpha"].id

    headers = {"X-Workspace-Id": alpha_id, "X-CSRF-Token": csrf_token}

    # 2. Create ticket
    payload = {
        "subject": "Unable to export monthly invoice PDF",
        "description": "Clicking download yields a 504 gateway timeout error.",
        "priority": "high",
        "category": "billing",
        "customer_email": "charlie@customer.com",
        "customer_name": "Charlie Customer",
    }
    create_res = await client.post("/api/tickets", json=payload, headers=headers, cookies=cookies)
    assert create_res.status_code == 201
    ticket = create_res.json()
    ticket_id = ticket["id"]
    assert ticket["subject"] == "Unable to export monthly invoice PDF"
    assert ticket["status"] == "open"
    assert ticket["priority"] == "high"
    assert len(ticket["messages"]) == 1  # initial message

    # 3. Post an internal note (Agent/Admin only)
    note_res = await client.post(
        f"/api/tickets/{ticket_id}/messages",
        json={"body": "Investigating PDF generator service in Kubernetes cluster.", "is_internal_note": True},
        headers=headers,
        cookies=cookies,
    )
    assert note_res.status_code == 201
    assert note_res.json()["is_internal_note"] is True

    # 4. Post public agent response
    reply_res = await client.post(
        f"/api/tickets/{ticket_id}/messages",
        json={"body": "Hi Charlie, our engineering team is actively looking into the PDF rendering timeout.", "is_internal_note": False},
        headers=headers,
        cookies=cookies,
    )
    assert reply_res.status_code == 201
    assert reply_res.json()["is_internal_note"] is False

    # 5. Fetch ticket as Agent -> Both public reply and internal note must be present
    fetch_res = await client.get(f"/api/tickets/{ticket_id}", headers={"X-Workspace-Id": alpha_id}, cookies=cookies)
    assert fetch_res.status_code == 200
    detail = fetch_res.json()
    assert len(detail["messages"]) == 3
    assert any(m["is_internal_note"] for m in detail["messages"])

    # 6. Fetch ticket as Customer via Portal -> Internal note MUST be redacted!
    portal_res = await client.get(
        f"/api/portal/tickets/{ticket_id}?email=charlie@customer.com&workspace_slug=alpha-corp"
    )
    assert portal_res.status_code == 200
    portal_detail = portal_res.json()
    assert len(portal_detail["messages"]) == 2  # initial + public reply (note stripped!)
    assert not any(m["is_internal_note"] for m in portal_detail["messages"])

    # 7. Update status to resolved
    update_res = await client.patch(
        f"/api/tickets/{ticket_id}",
        json={"status": "resolved"},
        headers=headers,
        cookies=cookies,
    )
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "resolved"
    assert update_res.json()["resolved_at"] is not None

@pytest.mark.asyncio
async def test_ticket_assignment(client: AsyncClient, seeded_entities: dict):
    """
    Verifies assigning ticket to a support agent within the active workspace,
    and rejecting assignment to users from outside workspaces.
    """
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "admin@alpha.com", "password": "Password123!"},
    )
    cookies = login_res.cookies
    csrf_token = login_res.json()["csrf_token"]
    alpha_id = seeded_entities["ws_alpha"].id
    headers = {"X-Workspace-Id": alpha_id, "X-CSRF-Token": csrf_token}

    # Create ticket
    create_res = await client.post(
        "/api/tickets",
        json={"subject": "Order delivery inquiry", "description": "Where is my package?"},
        headers=headers,
        cookies=cookies,
    )
    ticket_id = create_res.json()["id"]

    # Assign to Bob (Support Agent in Alpha)
    agent_id = seeded_entities["agent_alpha"].id
    assign_res = await client.post(
        f"/api/tickets/{ticket_id}/assign",
        json={"assigned_to_user_id": agent_id, "reason": "Handling shipping questions"},
        headers=headers,
        cookies=cookies,
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["assigned_agent_id"] == agent_id

    # Attempt to assign to Bella Beta (User from outside workspace Beta) -> Must return 400
    beta_user_id = seeded_entities["admin_beta"].id
    invalid_assign = await client.post(
        f"/api/tickets/{ticket_id}/assign",
        json={"assigned_to_user_id": beta_user_id},
        headers=headers,
        cookies=cookies,
    )
    assert invalid_assign.status_code == 400
    assert "not a member" in invalid_assign.json()["detail"].lower()

@pytest.mark.asyncio
async def test_cross_tenant_ticket_isolation(client: AsyncClient, seeded_entities: dict):
    """
    Verifies that a user from Workspace Beta CANNOT fetch, mutate, or view tickets in Workspace Alpha.
    """
    # 1. Create ticket in Alpha
    alpha_login = await client.post(
        "/api/auth/login",
        json={"email": "admin@alpha.com", "password": "Password123!"},
    )
    alpha_headers = {
        "X-Workspace-Id": seeded_entities["ws_alpha"].id,
        "X-CSRF-Token": alpha_login.json()["csrf_token"],
    }
    t_res = await client.post(
        "/api/tickets",
        json={"subject": "Confidential Alpha Ticket", "description": "Financial secrets"},
        headers=alpha_headers,
        cookies=alpha_login.cookies,
    )
    ticket_id = t_res.json()["id"]

    # 2. Login as Beta Admin
    beta_login = await client.post(
        "/api/auth/login",
        json={"email": "admin@beta.com", "password": "Password123!"},
    )
    beta_cookies = beta_login.cookies

    # 3. Attempt to fetch Alpha's ticket while passing Beta workspace
    res = await client.get(
        f"/api/tickets/{ticket_id}",
        headers={"X-Workspace-Id": seeded_entities["ws_beta"].id},
        cookies=beta_cookies,
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()
