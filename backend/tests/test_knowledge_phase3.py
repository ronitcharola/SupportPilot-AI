"""
Phase 3 tests: knowledge ingestion, upload validation, RBAC, tenant isolation,
reindex/delete lifecycle, retrieval preview and grounded chat escalation.
"""
import pytest
from sqlalchemy import func, select

from app.config import settings
from app.models.knowledge import DocumentChunk, KnowledgeDocument

REFUND_POLICY = """Refund Policy

Duplicate charges are refunded in full. We verify both transactions before proposing a refund.
Approved refunds return to the original payment method within 5 business days.
Annual plans can be refunded within 14 days of renewal when the workspace has had no recent logins.
Support agents may propose refunds up to $200; larger refunds need supervisor approval.
"""

SHIPPING_POLICY = """Shipping Policy

Orders placed before 2:00 PM ship the same business day.
Next-day shipping guarantees delivery on the next business day, not on weekends.
If tracking has not updated for 48 hours, open a carrier investigation with the order number.
"""


async def staff_session(factory, workspace_id: str, email: str = "admin@alpha.com"):
    client = factory()
    response = await client.post("/api/auth/login", json={"email": email, "password": "Password123!"})
    assert response.status_code == 200, response.text
    headers = {"X-Workspace-Id": workspace_id, "X-CSRF-Token": response.json()["csrf_token"]}
    return client, headers


async def add_text_document(client, headers, title: str, content: str) -> dict:
    response = await client.post(
        "/api/knowledge/documents/text",
        json={"title": title, "content": content},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_text_ingestion_search_and_stats(client_factory, seeded_entities: dict):
    alpha_id = seeded_entities["ws_alpha"].id
    client, headers = await staff_session(client_factory, alpha_id)

    document = await add_text_document(client, headers, "Refund Policy", REFUND_POLICY)
    assert document["status"] == "indexed"
    assert document["chunk_count"] >= 1
    assert document["embedding_provider"] == "mock"
    assert document["embedding_dimension"] == settings.EMBEDDING_DIMENSION
    assert document["uploaded_by_name"] == "Alice Alpha"

    detail = await client.get(
        f"/api/knowledge/documents/{document['id']}?include_chunks=true", headers=headers
    )
    assert detail.status_code == 200
    body = detail.json()
    assert len(body["chunks"]) == document["chunk_count"]
    assert [c["chunk_index"] for c in body["chunks"]] == list(range(document["chunk_count"]))
    assert "5 business days" in " ".join(c["content"] for c in body["chunks"])

    stats = (await client.get("/api/knowledge/stats", headers=headers)).json()
    assert stats["total_documents"] == 1
    assert stats["indexed_documents"] == 1
    assert stats["failed_documents"] == 0
    assert stats["total_chunks"] == document["chunk_count"]
    assert stats["embedding_provider"] == "mock"
    assert stats["total_characters"] >= len(REFUND_POLICY.strip()) - 5

    search = await client.post(
        "/api/knowledge/search",
        json={"query": "How long does a refund take?"},
        headers=headers,
    )
    assert search.status_code == 200
    results = search.json()
    assert results["provider"] == "mock"
    assert results["candidates_scanned"] >= 1
    assert results["results"], "the refund policy should be retrievable"
    assert results["results"][0]["document_id"] == document["id"]
    assert results["results"][0]["score"] >= results["threshold"]

    unrelated = await client.post(
        "/api/knowledge/search",
        json={"query": "What is the airspeed velocity of an unladen swallow?"},
        headers=headers,
    )
    assert unrelated.status_code == 200
    assert unrelated.json()["results"] == []

    empty = await client.post("/api/knowledge/search", json={"query": "R"}, headers=headers)
    assert empty.status_code == 422


@pytest.mark.asyncio
async def test_upload_validation_and_title(client_factory, seeded_entities: dict, monkeypatch):
    alpha_id = seeded_entities["ws_alpha"].id
    client, headers = await staff_session(client_factory, alpha_id)

    upload = await client.post(
        "/api/knowledge/documents",
        files={"file": ("shipping-policy.txt", SHIPPING_POLICY.encode(), "text/plain")},
        data={"title": "Shipping Doc"},
        headers=headers,
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["title"] == "Shipping Doc"
    assert body["source_type"] == "upload"
    assert body["filename"] == "shipping-policy.txt"
    assert body["status"] == "indexed"

    default_title = await client.post(
        "/api/knowledge/documents",
        files={"file": ("returns_and_refunds.md", REFUND_POLICY.encode(), "text/markdown")},
        headers=headers,
    )
    assert default_title.status_code == 201
    assert default_title.json()["title"] == "returns and refunds"

    unsupported = await client.post(
        "/api/knowledge/documents",
        files={"file": ("payload.exe", b"MZ\x90\x00binary", "application/octet-stream")},
        headers=headers,
    )
    assert unsupported.status_code == 415
    assert "Unsupported file type" in unsupported.json()["detail"]

    empty = await client.post(
        "/api/knowledge/documents",
        files={"file": ("empty.txt", b"", "text/plain")},
        headers=headers,
    )
    assert empty.status_code == 400

    short_text = await client.post(
        "/api/knowledge/documents/text",
        json={"title": "Too short", "content": "tiny"},
        headers=headers,
    )
    assert short_text.status_code == 422

    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 200)
    oversized = await client.post(
        "/api/knowledge/documents",
        files={"file": ("big.txt", b"refund policy " * 100, "text/plain")},
        headers=headers,
    )
    assert oversized.status_code == 413


@pytest.mark.asyncio
async def test_knowledge_rbac(client_factory, seeded_entities: dict):
    alpha_id = seeded_entities["ws_alpha"].id
    agent, agent_headers = await staff_session(
        client_factory, alpha_id, email="agent@alpha.com"
    )
    admin, admin_headers = await staff_session(client_factory, alpha_id)

    document = await add_text_document(admin, admin_headers, "Refund Policy", REFUND_POLICY)

    # Support agents may read, list, preview retrieval and view stats.
    assert (await agent.get("/api/knowledge/documents", headers=agent_headers)).status_code == 200
    assert (await agent.get("/api/knowledge/stats", headers=agent_headers)).status_code == 200
    assert (
        await agent.get(f"/api/knowledge/documents/{document['id']}", headers=agent_headers)
    ).status_code == 200
    assert (
        await agent.post(
            "/api/knowledge/search", json={"query": "refund timeline"}, headers=agent_headers
        )
    ).status_code == 200

    # But only admins may upload, reindex or delete knowledge.
    assert (
        await agent.post(
            "/api/knowledge/documents/text",
            json={"title": "Agent upload", "content": REFUND_POLICY},
            headers=agent_headers,
        )
    ).status_code == 403
    assert (
        await agent.post(
            f"/api/knowledge/documents/{document['id']}/reindex", headers=agent_headers
        )
    ).status_code == 403
    assert (
        await agent.delete(f"/api/knowledge/documents/{document['id']}", headers=agent_headers)
    ).status_code == 403

    anonymous = client_factory()
    assert (await anonymous.get("/api/knowledge/documents")).status_code == 401
    assert (await anonymous.get("/api/knowledge/stats")).status_code == 401
    # Mutating routes hit the CSRF gate before authentication.
    assert (
        await anonymous.post(
            "/api/knowledge/documents/text",
            json={"title": "Anonymous", "content": REFUND_POLICY},
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_knowledge_is_workspace_scoped(client_factory, seeded_entities: dict):
    alpha_id = seeded_entities["ws_alpha"].id
    beta_id = seeded_entities["ws_beta"].id
    alpha, alpha_headers = await staff_session(client_factory, alpha_id)
    beta, beta_headers = await staff_session(client_factory, beta_id, email="admin@beta.com")

    alpha_doc = await add_text_document(alpha, alpha_headers, "Refund Policy", REFUND_POLICY)
    await add_text_document(beta, beta_headers, "Shipping Policy", SHIPPING_POLICY)

    beta_list = (await beta.get("/api/knowledge/documents", headers=beta_headers)).json()
    assert [doc["title"] for doc in beta_list["items"]] == ["Shipping Policy"]
    assert beta_list["items"][0]["id"] != alpha_doc["id"]

    # Cross-tenant reads, writes and deletes all look like a missing resource.
    assert (
        await beta.get(f"/api/knowledge/documents/{alpha_doc['id']}", headers=beta_headers)
    ).status_code == 404
    assert (
        await beta.post(
            f"/api/knowledge/documents/{alpha_doc['id']}/reindex", headers=beta_headers
        )
    ).status_code == 404
    assert (
        await beta.delete(f"/api/knowledge/documents/{alpha_doc['id']}", headers=beta_headers)
    ).status_code == 404

    # Retrieval never crosses the boundary, even for identical questions.
    beta_search = await beta.post(
        "/api/knowledge/search",
        json={"query": "How long does a refund take?"},
        headers=beta_headers,
    )
    assert beta_search.status_code == 200
    assert all(
        hit["document_id"] != alpha_doc["id"] for hit in beta_search.json()["results"]
    )

    beta_chat = await beta.post(
        "/api/ai/chat",
        json={
            "message": "How do I configure the Okta metadata URL for SAML?",
            "workspace_slug": "beta-corp",
        },
    )
    assert beta_chat.status_code == 200
    assert beta_chat.json()["escalated"] is True
    assert beta_chat.json()["citations"] == []


@pytest.mark.asyncio
async def test_grounded_chat_citations_and_escalation(client_factory, seeded_entities: dict):
    alpha_id = seeded_entities["ws_alpha"].id
    client, headers = await staff_session(client_factory, alpha_id)
    document = await add_text_document(client, headers, "Refund Policy", REFUND_POLICY)

    grounded = await client.post(
        "/api/ai/chat",
        json={"message": "How long does a refund take to arrive?", "workspace_slug": "alpha-corp"},
    )
    assert grounded.status_code == 200, grounded.text
    body = grounded.json()
    assert body["grounded"] is True
    assert body["escalated"] is False
    assert body["citations"], "grounded answers must carry citations"
    citation = body["citations"][0]
    assert citation["document_id"] == document["id"]
    assert citation["document_title"] == "Refund Policy"
    assert citation["number"] >= 1
    assert 0 < citation["score"] <= 1
    assert citation["excerpt"]
    assert "[" in body["answer"] and "]" in body["answer"]
    assert body["provider"] == "mock"
    assert body["threshold"] == settings.MOCK_SIMILARITY_THRESHOLD

    escalated = await client.post(
        "/api/ai/chat",
        json={"message": "What is the capital of France?", "workspace_slug": "alpha-corp"},
    )
    assert escalated.status_code == 200
    escalation = escalated.json()
    assert escalation["grounded"] is False
    assert escalation["escalated"] is True
    assert escalation["citations"] == []
    assert "human support agent" in escalation["answer"]
    assert "France" not in escalation["answer"]

    unknown_workspace = await client.post(
        "/api/ai/chat",
        json={"message": "Where is my order?", "workspace_slug": "ghost-co"},
    )
    assert unknown_workspace.status_code == 404

    bad_request = await client.post("/api/ai/chat", json={"message": "x", "workspace_slug": "alpha-corp"})
    assert bad_request.status_code == 422


@pytest.mark.asyncio
async def test_reindex_and_delete_lifecycle(client_factory, seeded_entities: dict, db_session):
    alpha_id = seeded_entities["ws_alpha"].id
    client, headers = await staff_session(client_factory, alpha_id)
    document = await add_text_document(client, headers, "Refund Policy", REFUND_POLICY)

    chunks_before = (
        await db_session.execute(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document["id"])
        )
    ).scalar_one()
    assert chunks_before == document["chunk_count"]

    reindexed = await client.post(
        f"/api/knowledge/documents/{document['id']}/reindex", headers=headers
    )
    assert reindexed.status_code == 200
    assert reindexed.json()["status"] == "indexed"
    chunks_after = (
        await db_session.execute(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document["id"])
        )
    ).scalar_one()
    assert chunks_after == chunks_before

    deleted = await client.delete(f"/api/knowledge/documents/{document['id']}", headers=headers)
    assert deleted.status_code == 204
    assert (
        await client.get(f"/api/knowledge/documents/{document['id']}", headers=headers)
    ).status_code == 404
    assert (
        await db_session.execute(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document["id"])
        )
    ).scalar_one() == 0
    assert (
        await db_session.execute(
            select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.id == document["id"])
        )
    ).scalar_one() == 0


@pytest.mark.asyncio
async def test_document_list_filters_and_pagination(client_factory, seeded_entities: dict):
    client, headers = await staff_session(client_factory, seeded_entities["ws_alpha"].id)
    await add_text_document(client, headers, "Refund Policy", REFUND_POLICY)
    await add_text_document(client, headers, "Shipping Policy", SHIPPING_POLICY)

    listing = (await client.get("/api/knowledge/documents", headers=headers)).json()
    assert listing["total"] == 2
    assert listing["total_pages"] == 1

    filtered = await client.get("/api/knowledge/documents?search=shipping", headers=headers)
    assert filtered.status_code == 200
    assert [doc["title"] for doc in filtered.json()["items"]] == ["Shipping Policy"]

    sorted_asc = await client.get(
        "/api/knowledge/documents?sort_by=title&sort_order=asc", headers=headers
    )
    assert [doc["title"] for doc in sorted_asc.json()["items"]] == [
        "Refund Policy",
        "Shipping Policy",
    ]

    paged = await client.get("/api/knowledge/documents?page=1&page_size=1", headers=headers)
    assert paged.json()["total_pages"] == 2
    assert len(paged.json()["items"]) == 1

    assert (await client.get("/api/knowledge/documents?page=0", headers=headers)).status_code == 422
    assert (
        await client.get("/api/knowledge/documents?status=bogus", headers=headers)
    ).status_code == 422
    assert (
        await client.get("/api/knowledge/documents?sort_by=source_text", headers=headers)
    ).status_code == 422
