"""
Phase 4 tests: AI classification, escalation policy, apply/reclassify,
grounded suggestion drafts, portal redaction and provider-failure resilience.
"""
import json

import pytest
from sqlalchemy import select

from app.ai.base import LLMResponse, ProviderError
from app.ai.classifier import (
    VALID_CATEGORIES,
    VALID_PRIORITIES,
    VALID_SENTIMENTS,
    LLMTicketClassifier,
    MockTicketClassifier,
)
from app.models.workspace import WorkspaceSettings
from app.services import ticket_service, triage_service

REFUND_POLICY = """Refund Policy

Duplicate charges are refunded in full. Approved refunds return to the original payment
method within 5 business days. Agents may propose refunds up to $200; larger refunds need
supervisor approval.
"""


async def staff_session(factory, workspace_id: str, email: str = "admin@alpha.com"):
    client = factory()
    response = await client.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    assert response.status_code == 200, response.text
    return client, {"X-Workspace-Id": workspace_id, "X-CSRF-Token": response.json()["csrf_token"]}


async def create_ticket(client, headers, **overrides) -> dict:
    payload = {
        "subject": "Printer will not connect",
        "description": "The office printer rejects every connection attempt since this morning.",
        "priority": "medium",
        "category": "technical_issues",
        "customer_email": "casey@customer.com",
        "customer_name": "Casey Customer",
    }
    payload.update(overrides)
    response = await client.post("/api/tickets", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def add_policy(client, headers):
    response = await client.post(
        "/api/knowledge/documents/text",
        json={"title": "Refund Policy", "content": REFUND_POLICY},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_creation_classifies_and_escalates_sensitive_ticket(client_factory, seeded_entities: dict):
    client, headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    ticket = await create_ticket(
        client,
        headers,
        subject="Charged twice for the same invoice",
        description=(
            "We were billed twice this month for invoice 4471 and need the duplicate charge refunded. "
            "This is unacceptable."
        ),
        category="billing",
    )

    assert ticket["status"] == "open", "triage must not move the ticket status"
    assert ticket["is_escalated"] is True
    assert ticket["escalation_reason"]
    assert ticket["ai_intent"] == "duplicate_charge_refund"
    assert ticket["ai_sentiment"] in ("concerned", "frustrated", "angry")
    assert ticket["ai_confidence"] is not None and ticket["ai_confidence"] >= 0.6
    assert ticket["ai_urgency_score"] is not None and ticket["ai_urgency_score"] >= 0.8
    assert ticket["ai_escalation_reasons"], "escalation reasons must be exposed to staff"
    assert any("duplicate_charge_refund" in reason or "refund" in reason.lower() for reason in ticket["ai_escalation_reasons"])
    assert ticket["ai_summary"]
    assert ticket["ai_suggested_category"] == "refunds"
    assert ticket["ai_suggested_priority"] in VALID_PRIORITIES

    escalated = await client.get("/api/tickets?escalated=true", headers=headers)
    assert escalated.status_code == 200
    assert [item["id"] for item in escalated.json()["items"]] == [ticket["id"]]

    unescalated = await client.get("/api/tickets?escalated=false", headers=headers)
    assert unescalated.json()["total"] == 1  # filter off returns everything


@pytest.mark.asyncio
async def test_non_sensitive_inquiry_is_not_escalated(client_factory, seeded_entities: dict):
    client, headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    ticket = await create_ticket(
        client,
        headers,
        subject="How do I export a CSV report?",
        description="I would like to know how to export the monthly report for our finance team.",
        category="product_questions",
        priority="low",
    )

    assert ticket["is_escalated"] is False
    assert ticket["escalation_reason"] is None
    assert ticket["ai_intent"] == "feature_question"
    assert ticket["ai_sentiment"] in ("neutral", "positive")
    assert ticket["ai_urgency_score"] < 0.5
    assert ticket["ai_summary"]


@pytest.mark.asyncio
async def test_angry_customer_escalates(client_factory, seeded_entities: dict):
    client, headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    ticket = await create_ticket(
        client,
        headers,
        subject="Still no response",
        description="This is unacceptable. Third time I am contacting you and still no response.",
        category="other",
    )

    assert ticket["ai_sentiment"] == "angry"
    assert ticket["is_escalated"] is True
    assert "angry" in " ".join(ticket["ai_escalation_reasons"]).lower()


@pytest.mark.asyncio
async def test_human_request_escalates(client_factory, seeded_entities: dict):
    client, headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    ticket = await create_ticket(
        client,
        headers,
        subject="Need a person",
        description="Please let me speak to a real person about my subscription.",
        category="other",
    )

    assert ticket["ai_intent"] == "human_handoff"
    assert ticket["is_escalated"] is True
    assert any("human" in reason.lower() for reason in ticket["ai_escalation_reasons"])


@pytest.mark.asyncio
async def test_low_confidence_escalates(client_factory, seeded_entities: dict):
    client, headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    ticket = await create_ticket(
        client,
        headers,
        subject="Hello",
        description="I have something to discuss with your team when convenient.",
        category="other",
    )

    assert ticket["ai_confidence"] < 0.55
    assert ticket["is_escalated"] is True
    assert any("confidence" in reason.lower() for reason in ticket["ai_escalation_reasons"])


@pytest.mark.asyncio
async def test_reclassify_and_apply_suggested_fields(client_factory, seeded_entities: dict):
    alpha_id = seeded_entities["ws_alpha"].id
    client, headers = await staff_session(client_factory, alpha_id)
    ticket = await create_ticket(
        client,
        headers,
        subject="Billing question",
        description="Please explain the duplicate charge on invoice 991.",
        category="product_questions",
        priority="low",
    )
    assert ticket["category"] == "product_questions"
    assert ticket["priority"] == "low"
    assert ticket["ai_suggested_category"] == "refunds"

    reclassified = await client.post(f"/api/tickets/{ticket['id']}/classify", headers=headers)
    assert reclassified.status_code == 200
    body = reclassified.json()
    assert body["category"] == "product_questions", "classify without apply must not overwrite fields"
    assert body["priority"] == "low"
    assert body["ai_suggested_category"] == "refunds"

    applied = await client.post(f"/api/tickets/{ticket['id']}/classify?apply=true", headers=headers)
    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["category"] == "refunds"
    assert applied_body["priority"] in ("high", "urgent")
    assert applied_body["is_escalated"] is True

    beta, beta_headers = await staff_session(client_factory, seeded_entities["ws_beta"].id, "admin@beta.com")
    assert (
        await beta.post(f"/api/tickets/{ticket['id']}/classify", headers=beta_headers)
    ).status_code == 404

    agent, agent_headers = await staff_session(client_factory, alpha_id, "agent@alpha.com")
    assert (
        await agent.post(f"/api/tickets/{ticket['id']}/classify", headers=agent_headers)
    ).status_code == 200

    anonymous = client_factory()
    assert (
        await anonymous.post(f"/api/tickets/{ticket['id']}/classify")
    ).status_code == 403  # CSRF gate before authentication


@pytest.mark.asyncio
async def test_portal_creation_classifies_but_hides_internal_metadata(client_factory, seeded_entities: dict):
    anonymous = client_factory()
    response = await anonymous.post(
        "/api/portal/tickets?workspace_slug=alpha-corp",
        json={
            "subject": "Duplicate charge on my card",
            "description": "I was charged twice for the same order and need a refund.",
            "customer_email": "gina@customer.com",
            "customer_name": "Gina Customer",
            "category": "refunds",
        },
    )
    assert response.status_code == 201, response.text
    portal_ticket = response.json()

    # Customers never receive internal AI metadata or escalation reasons.
    assert portal_ticket["ai_intent"] is None
    assert portal_ticket["ai_summary"] is None
    assert portal_ticket["ai_confidence"] is None
    assert portal_ticket["ai_escalation_reasons"] == []
    assert portal_ticket["is_escalated"] is False
    assert portal_ticket["escalation_reason"] is None
    assert "Duplicate charge" not in json.dumps(portal_ticket["ai_escalation_reasons"])

    staff, staff_headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    detail = await staff.get(f"/api/tickets/{portal_ticket['id']}", headers=staff_headers)
    assert detail.status_code == 200
    staff_view = detail.json()
    assert staff_view["ai_intent"] == "duplicate_charge_refund"
    assert staff_view["is_escalated"] is True
    assert staff_view["ai_escalation_reasons"]

    listing = await anonymous.get(
        "/api/portal/tickets?email=gina@customer.com&workspace_slug=alpha-corp"
    )
    assert listing.status_code == 200
    assert listing.json()[0]["ai_intent"] is None
    assert listing.json()[0]["ai_escalation_reasons"] == []


@pytest.mark.asyncio
async def test_suggested_reply_is_grounded_and_not_persisted(client_factory, seeded_entities: dict):
    alpha_id = seeded_entities["ws_alpha"].id
    client, headers = await staff_session(client_factory, alpha_id)
    document = await add_policy(client, headers)

    ticket = await create_ticket(
        client,
        headers,
        subject="When will my refund arrive?",
        description="I was charged twice and want to know how long the refund takes.",
        category="refunds",
    )
    messages_before = len(ticket["messages"])

    response = await client.post(f"/api/tickets/{ticket['id']}/suggested-reply", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["grounded"] is True
    assert body["draft"]
    assert body["draft"].startswith("Hi ")
    assert "[1]" in body["draft"]
    assert body["citations"]
    assert body["citations"][0]["document_id"] == document["id"]
    assert body["citations"][0]["document_title"] == "Refund Policy"
    assert body["provider"] == "mock"
    assert body["note"] and "draft" in body["note"].lower()

    # The draft must never be saved or sent.
    refreshed = await client.get(f"/api/tickets/{ticket['id']}", headers=headers)
    assert len(refreshed.json()["messages"]) == messages_before

    beta, beta_headers = await staff_session(client_factory, seeded_entities["ws_beta"].id, "admin@beta.com")
    assert (
        await beta.post(f"/api/tickets/{ticket['id']}/suggested-reply", headers=beta_headers)
    ).status_code == 404

    agent, agent_headers = await staff_session(client_factory, alpha_id, "agent@alpha.com")
    assert (
        await agent.post(f"/api/tickets/{ticket['id']}/suggested-reply", headers=agent_headers)
    ).status_code == 200

    anonymous = client_factory()
    assert (
        await anonymous.post(f"/api/tickets/{ticket['id']}/suggested-reply")
    ).status_code == 401


@pytest.mark.asyncio
async def test_suggested_reply_without_evidence(client_factory, seeded_entities: dict):
    client, headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    ticket = await create_ticket(
        client,
        headers,
        subject="Unrelated question",
        description="Please explain the airspeed velocity of an unladen swallow.",
        category="other",
    )

    response = await client.post(f"/api/tickets/{ticket['id']}/suggested-reply", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is False
    assert body["draft"] is None
    assert body["citations"] == []
    assert body["note"]


@pytest.mark.asyncio
async def test_workspace_threshold_controls_escalation(
    client_factory, seeded_entities: dict, db_session
):
    alpha_id = seeded_entities["ws_alpha"].id
    client, headers = await staff_session(client_factory, alpha_id)

    settings_row = (
        await db_session.execute(
            select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == alpha_id)
        )
    ).scalar_one()
    settings_row.auto_escalate_urgency_threshold = 0.95
    await db_session.commit()

    ticket = await create_ticket(
        client,
        headers,
        subject="Site is completely down",
        description="All checkout requests return 503 after the deploy.",
        category="technical_issues",
    )
    assert ticket["ai_urgency_score"] and ticket["ai_urgency_score"] < 0.95
    assert ticket["is_escalated"] is False

    settings_row.auto_escalate_urgency_threshold = 0.5
    await db_session.commit()

    reclassified = await client.post(f"/api/tickets/{ticket['id']}/classify", headers=headers)
    assert reclassified.status_code == 200
    assert reclassified.json()["is_escalated"] is True
    assert any("threshold" in reason.lower() for reason in reclassified.json()["ai_escalation_reasons"])


@pytest.mark.asyncio
async def test_provider_failure_does_not_block_creation(
    client_factory, seeded_entities: dict, monkeypatch
):
    client, headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)

    async def failing_classifier(*args, **kwargs):
        raise ProviderError("AI provider is offline for this test.")

    monkeypatch.setattr(triage_service, "classify_ticket", failing_classifier)
    # ticket_service imported the function indirectly through apply_ai_triage, so the
    # monkeypatch above is the function it calls at runtime.

    ticket = await create_ticket(client, headers, subject="Charged twice", description="Please refund the duplicate charge.")
    assert ticket["ai_summary"] is None
    assert ticket["ai_intent"] is None
    assert ticket["is_escalated"] is False

    explicit = await client.post(f"/api/tickets/{ticket['id']}/classify", headers=headers)
    assert explicit.status_code == 503
    assert "unavailable" in explicit.json()["detail"].lower()


@pytest.mark.asyncio
async def test_mock_classifier_is_deterministic_and_valid():
    classifier = MockTicketClassifier()
    subject = "Charged twice and need a refund"
    body = "Our finance team sees two charges for invoice 4471. This is unacceptable."

    first = await classifier.classify(subject, body)
    second = await classifier.classify(subject, body)
    assert first == second
    assert first.category in VALID_CATEGORIES
    assert first.priority in VALID_PRIORITIES
    assert first.sentiment in VALID_SENTIMENTS
    assert 0.0 <= first.confidence <= 1.0
    assert 0.0 <= first.urgency_score <= 1.0
    assert first.intent == "duplicate_charge_refund"
    assert first.provider == "mock"

    # Category/priority vocabularies must not drift from the ticket service.
    assert set(VALID_CATEGORIES) == set(ticket_service.TICKET_CATEGORIES)
    assert set(VALID_PRIORITIES) == set(ticket_service.TICKET_PRIORITIES)


class _StubLLM:
    name = "openai"
    model = "stub-model"

    def __init__(self, content: str):
        self.content = content

    async def complete(self, system_prompt, user_prompt, *, max_tokens=800, temperature=0.2):
        return LLMResponse(content=self.content, provider=self.name, model=self.model)


@pytest.mark.asyncio
async def test_llm_classifier_parses_strict_json():
    payload = {
        "category": "refunds",
        "priority": "high",
        "sentiment": "concerned",
        "intent": "refund_request",
        "confidence": 0.91,
        "summary": "Customer requests a refund for a duplicate charge.",
        "urgency_score": 0.8,
        "requested_human": False,
    }
    classifier = LLMTicketClassifier(_StubLLM(f"```json\n{json.dumps(payload)}\n```"))
    result = await classifier.classify("Refund", "I was charged twice.")
    assert result.category == "refunds"
    assert result.priority == "high"
    assert result.confidence == 0.91
    assert result.provider == "openai"

    with pytest.raises(ProviderError):
        await LLMTicketClassifier(_StubLLM("not json at all")).classify("x", "y")

    invalid = await LLMTicketClassifier(
        _StubLLM(
            json.dumps(
                {
                    "category": "bogus",
                    "priority": "bogus",
                    "sentiment": "bogus",
                    "intent": "Some Intent!",
                    "confidence": 0.5,
                    "summary": "Summary.",
                    "urgency_score": 0.4,
                    "requested_human": False,
                }
            )
        )
    ).classify("x", "y")
    assert invalid.category == "other"
    assert invalid.priority == "medium"
    assert invalid.sentiment == "neutral"
    assert invalid.intent == "some_intent"
