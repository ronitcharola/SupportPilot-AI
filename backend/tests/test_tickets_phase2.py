"""
Phase 2 ticket management tests: lifecycle validation, enum validation,
filtering, sorting, pagination, role restrictions and portal isolation.
"""
import pytest
from httpx import AsyncClient

from app.models.ticket import Ticket, TicketMessage


async def staff_session(factory, workspace_id: str, email: str = "admin@alpha.com"):
    """Logs in through a dedicated client so cookie + CSRF state stays per identity."""
    client = factory()
    res = await client.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    assert res.status_code == 200, res.text
    headers = {"X-Workspace-Id": workspace_id, "X-CSRF-Token": res.json()["csrf_token"]}
    return client, headers


async def create_ticket(client: AsyncClient, headers: dict, **overrides) -> dict:
    payload = {
        "subject": "Printer will not connect",
        "description": "The office printer rejects every connection attempt since this morning.",
        "priority": "medium",
        "category": "technical_issues",
        "customer_email": "casey@customer.com",
        "customer_name": "Casey Customer",
    }
    payload.update(overrides)
    res = await client.post("/api/tickets", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.asyncio
async def test_status_transitions_are_validated(client_factory, seeded_entities: dict):
    client, headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    ticket = await create_ticket(client, headers)
    ticket_id = ticket["id"]
    assert ticket["status"] == "open"
    assert "in_progress" in ticket["allowed_transitions"]
    assert "pending_approval" in ticket["allowed_transitions"]

    # open -> pending_approval is legal
    res = await client.patch(f"/api/tickets/{ticket_id}", json={"status": "pending_approval"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "pending_approval"

    # pending_approval -> open is illegal (the 409 lists the legal exits)
    res = await client.patch(f"/api/tickets/{ticket_id}", json={"status": "open"}, headers=headers)
    assert res.status_code == 409
    assert "invalid status transition" in res.json()["detail"].lower()
    assert "in_progress" in res.json()["detail"]

    # pending_approval -> in_progress is legal
    res = await client.patch(f"/api/tickets/{ticket_id}", json={"status": "in_progress"}, headers=headers)
    assert res.status_code == 200

    # Resolve, then reopen only through 'open'
    res = await client.patch(f"/api/tickets/{ticket_id}", json={"status": "resolved"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["resolved_at"] is not None

    res = await client.patch(f"/api/tickets/{ticket_id}", json={"status": "in_progress"}, headers=headers)
    assert res.status_code == 409

    res = await client.patch(f"/api/tickets/{ticket_id}", json={"status": "open"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "open"
    assert res.json()["resolved_at"] is None


@pytest.mark.asyncio
async def test_enum_and_pagination_validation(client_factory, seeded_entities: dict):
    client, headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    ticket = await create_ticket(client, headers)
    ticket_id = ticket["id"]

    assert (await client.patch(f"/api/tickets/{ticket_id}", json={"status": "bogus"}, headers=headers)).status_code == 422
    assert (await client.patch(f"/api/tickets/{ticket_id}", json={"priority": "critical"}, headers=headers)).status_code == 422
    assert (await client.patch(f"/api/tickets/{ticket_id}", json={"category": "not_a_category"}, headers=headers)).status_code == 422

    bad_create = await client.post(
        "/api/tickets",
        json={"subject": "Bad category", "description": "Testing validation", "category": "nonsense"},
        headers=headers,
    )
    assert bad_create.status_code == 422

    short_create = await client.post(
        "/api/tickets",
        json={"subject": "x", "description": "y"},
        headers=headers,
    )
    assert short_create.status_code == 422

    empty_message = await client.post(
        f"/api/tickets/{ticket_id}/messages", json={"body": ""}, headers=headers
    )
    assert empty_message.status_code == 422

    assert (await client.get("/api/tickets?page=0", headers=headers)).status_code == 422
    assert (await client.get("/api/tickets?page_size=500", headers=headers)).status_code == 422
    assert (await client.get("/api/tickets?sort_by=password_hash", headers=headers)).status_code == 422


@pytest.mark.asyncio
async def test_filters_search_sort_and_pagination(client_factory, seeded_entities: dict):
    alpha_id = seeded_entities["ws_alpha"].id
    client, headers = await staff_session(client_factory, alpha_id)

    low = await create_ticket(
        client, headers,
        subject="Refund question about invoice",
        description="Please explain the duplicate line item on invoice 4471.",
        priority="low",
        category="billing",
        customer_email="dana@customer.com",
        customer_name="Dana Refunds",
    )
    urgent = await create_ticket(
        client, headers,
        subject="Site is completely down",
        description="All checkout requests return 503 since the deploy.",
        priority="urgent",
        category="technical_issues",
        customer_email="erin@customer.com",
        customer_name="Erin Ops",
    )
    medium = await create_ticket(
        client, headers,
        subject="Where is my order",
        description="Order 9182 has not shipped yet.",
        priority="medium",
        category="shipping",
        customer_email="frank@customer.com",
        customer_name="Frank Buyer",
    )

    agent_id = seeded_entities["agent_alpha"].id
    res = await client.post(
        f"/api/tickets/{urgent['id']}/assign",
        json={"assigned_to_user_id": agent_id, "reason": "Sev-1 incident"},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["assigned_agent_name"] == "Bob Alpha"

    # Status filter
    res = await client.get("/api/tickets?status=open", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] == 3

    # Priority filter
    res = await client.get("/api/tickets?priority=urgent", headers=headers)
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["id"] == urgent["id"]

    # Category filter
    res = await client.get("/api/tickets?category=shipping", headers=headers)
    assert [t["id"] for t in res.json()["items"]] == [medium["id"]]

    # Assignee filter and unassigned filter
    res = await client.get(f"/api/tickets?assignee_id={agent_id}", headers=headers)
    assert [t["id"] for t in res.json()["items"]] == [urgent["id"]]

    res = await client.get("/api/tickets?unassigned=true", headers=headers)
    assert {t["id"] for t in res.json()["items"]} == {low["id"], medium["id"]}

    # Search by customer name and email, not just subject
    res = await client.get("/api/tickets?search=Dana", headers=headers)
    assert [t["id"] for t in res.json()["items"]] == [low["id"]]

    res = await client.get("/api/tickets?search=frank@customer.com", headers=headers)
    assert [t["id"] for t in res.json()["items"]] == [medium["id"]]

    # Sorting by priority ascending puts low first and urgent last
    res = await client.get("/api/tickets?sort_by=priority&sort_order=asc", headers=headers)
    priorities = [t["priority"] for t in res.json()["items"]]
    assert priorities == ["low", "medium", "urgent"]

    res = await client.get("/api/tickets?sort_by=ticket_number&sort_order=desc", headers=headers)
    numbers = [t["ticket_number"] for t in res.json()["items"]]
    assert numbers == sorted(numbers, reverse=True)

    # Pagination
    res = await client.get("/api/tickets?page=1&page_size=2", headers=headers)
    body = res.json()
    assert body["total"] == 3
    assert body["total_pages"] == 2
    assert len(body["items"]) == 2

    res = await client.get("/api/tickets?page=2&page_size=2", headers=headers)
    body = res.json()
    assert body["page"] == 2
    assert len(body["items"]) == 1


@pytest.mark.asyncio
async def test_agent_reply_moves_ticket_to_waiting_for_customer(client_factory, seeded_entities: dict):
    client, headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    ticket = await create_ticket(client, headers)

    # Internal notes never change customer-facing state
    res = await client.post(
        f"/api/tickets/{ticket['id']}/messages",
        json={"body": "Checked the printer queue, nothing stuck.", "is_internal_note": True},
        headers=headers,
    )
    assert res.status_code == 201
    assert (await client.get(f"/api/tickets/{ticket['id']}", headers=headers)).json()["status"] == "open"

    # A public reply hands the conversation back to the customer
    res = await client.post(
        f"/api/tickets/{ticket['id']}/messages",
        json={"body": "Could you power-cycle the printer and confirm the LED state?", "is_internal_note": False},
        headers=headers,
    )
    assert res.status_code == 201
    assert (await client.get(f"/api/tickets/{ticket['id']}", headers=headers)).json()["status"] == "waiting_for_customer"

    # The message thread endpoint returns the whole thread for staff
    res = await client.get(f"/api/tickets/{ticket['id']}/messages", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 3  # initial customer message + internal note + reply


@pytest.mark.asyncio
async def test_unauthenticated_customer_cannot_use_internal_ticket_api(client_factory, seeded_entities: dict):
    client, headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    ticket = await create_ticket(client, headers)

    anonymous = client_factory()
    assert (await anonymous.get("/api/tickets")).status_code == 401
    assert (await anonymous.get(f"/api/tickets/{ticket['id']}")).status_code == 401
    assert (await anonymous.get(f"/api/tickets/{ticket['id']}/messages")).status_code == 401
    # Mutations hit the CSRF gate before the auth dependency, so they are rejected with 403.
    assert (await anonymous.patch(f"/api/tickets/{ticket['id']}", json={"status": "resolved"})).status_code == 403
    assert (
        await anonymous.post(f"/api/tickets/{ticket['id']}/messages", json={"body": "hi", "is_internal_note": True})
    ).status_code == 403


@pytest.mark.asyncio
async def test_customer_cannot_read_other_customers_tickets(client_factory, seeded_entities: dict):
    anonymous = client_factory()

    first = await anonymous.post(
        "/api/portal/tickets?workspace_slug=alpha-corp",
        json={
            "subject": "Alice private billing issue",
            "description": "My card ending 4242 was charged twice.",
            "customer_email": "alice@customer.com",
            "customer_name": "Alice Customer",
            "category": "billing",
        },
    )
    assert first.status_code == 201, first.text
    first_ticket = first.json()

    second = await anonymous.post(
        "/api/portal/tickets?workspace_slug=alpha-corp",
        json={
            "subject": "Bob private shipping issue",
            "description": "My parcel never arrived.",
            "customer_email": "bob@customer.com",
            "customer_name": "Bob Customer",
            "category": "shipping",
        },
    )
    assert second.status_code == 201, second.text

    # Bob may not read Alice's ticket even with the exact id
    res = await anonymous.get(
        f"/api/portal/tickets/{first_ticket['id']}?email=bob@customer.com&workspace_slug=alpha-corp"
    )
    assert res.status_code == 404

    # Bob's listing contains only his own ticket
    res = await anonymous.get("/api/portal/tickets?email=bob@customer.com&workspace_slug=alpha-corp")
    assert res.status_code == 200
    assert [t["subject"] for t in res.json()] == ["Bob private shipping issue"]

    # Cross-workspace portal access is refused outright
    res = await anonymous.get(
        f"/api/portal/tickets/{first_ticket['id']}?email=alice@customer.com&workspace_slug=beta-corp"
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_portal_never_exposes_internal_notes(client_factory, seeded_entities: dict):
    client, headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    ticket = await create_ticket(client, headers, customer_email="gina@customer.com", customer_name="Gina")

    note = await client.post(
        f"/api/tickets/{ticket['id']}/messages",
        json={"body": "Secret internal escalation: finance must approve.", "is_internal_note": True},
        headers=headers,
    )
    assert note.status_code == 201

    anonymous = client_factory()
    detail = await anonymous.get(
        f"/api/portal/tickets/{ticket['id']}?email=gina@customer.com&workspace_slug=alpha-corp"
    )
    assert detail.status_code == 200
    assert all(not m["is_internal_note"] for m in detail.json()["messages"])
    assert "Secret internal escalation" not in detail.text

    listing = await anonymous.get("/api/portal/tickets?email=gina@customer.com&workspace_slug=alpha-corp")
    assert "Secret internal escalation" not in listing.text

    # A customer reply can never be flagged as an internal note
    reply = await anonymous.post(
        f"/api/portal/tickets/{ticket['id']}/messages?email=gina@customer.com&workspace_slug=alpha-corp",
        json={"body": "Any update?", "is_internal_note": True},
    )
    assert reply.status_code == 201
    assert reply.json()["is_internal_note"] is False

    # Other customers cannot post into this ticket
    other = await anonymous.post(
        f"/api/portal/tickets/{ticket['id']}/messages?email=intruder@customer.com&workspace_slug=alpha-corp",
        json={"body": "I should not be here."},
    )
    assert other.status_code == 404


@pytest.mark.asyncio
async def test_cross_workspace_mutations_are_blocked(client_factory, seeded_entities: dict):
    alpha, alpha_headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    ticket = await create_ticket(alpha, alpha_headers)

    beta, beta_headers = await staff_session(
        client_factory, seeded_entities["ws_beta"].id, email="admin@beta.com"
    )
    target = f"/api/tickets/{ticket['id']}"

    assert (await beta.get(target, headers=beta_headers)).status_code == 404
    assert (await beta.patch(target, json={"status": "in_progress"}, headers=beta_headers)).status_code == 404
    assert (
        await beta.post(f"{target}/messages", json={"body": "beta intrusion"}, headers=beta_headers)
    ).status_code == 404
    assert (
        await beta.post(
            f"{target}/assign",
            json={"assigned_to_user_id": seeded_entities["admin_beta"].id},
            headers=beta_headers,
        )
    ).status_code == 404
    assert (await beta.get(f"{target}/messages", headers=beta_headers)).status_code == 404


@pytest.mark.asyncio
async def test_workspace_scoped_ticket_numbers(client_factory, seeded_entities: dict):
    alpha, alpha_headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    beta, beta_headers = await staff_session(
        client_factory, seeded_entities["ws_beta"].id, email="admin@beta.com"
    )

    alpha_ticket = await create_ticket(alpha, alpha_headers)
    beta_ticket = await create_ticket(beta, beta_headers)

    assert alpha_ticket["ticket_number"] == 1001
    assert beta_ticket["ticket_number"] == 1001
    assert alpha_ticket["workspace_id"] != beta_ticket["workspace_id"]


@pytest.mark.asyncio
async def test_customer_records_are_workspace_scoped(client_factory, seeded_entities: dict, db_session):
    alpha, alpha_headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    beta, beta_headers = await staff_session(
        client_factory, seeded_entities["ws_beta"].id, email="admin@beta.com"
    )

    await create_ticket(alpha, alpha_headers, customer_email="shared@customer.com", customer_name="Shared Alpha")
    await create_ticket(beta, beta_headers, customer_email="shared@customer.com", customer_name="Shared Beta")

    rows = (await db_session.execute(Ticket.__table__.select())).all()
    assert len(rows) == 2
    assert len({row.customer_id for row in rows}) == 2  # same email, two tenant-scoped customers

    alpha_list = (await alpha.get("/api/tickets", headers=alpha_headers)).json()
    beta_list = (await beta.get("/api/tickets", headers=beta_headers)).json()
    assert alpha_list["total"] == 1
    assert beta_list["total"] == 1
    assert alpha_list["items"][0]["customer_name"] == "Shared Alpha"
    assert beta_list["items"][0]["customer_name"] == "Shared Beta"
