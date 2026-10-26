import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_cross_tenant_access_denied(client: AsyncClient, seeded_entities: dict):
    """
    Guarantees tenant isolation:
    A user belonging to Workspace Beta CANNOT access or query Workspace Alpha.
    """
    # 1. Login as Beta Admin
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "admin@beta.com", "password": "Password123!"},
    )
    assert login_res.status_code == 200
    cookies = login_res.cookies

    # 2. Attempt to read Alpha workspace settings by passing Alpha's workspace ID
    alpha_id = seeded_entities["ws_alpha"].id
    res = await client.get(
        "/api/workspaces/current/settings",
        headers={"X-Workspace-Id": alpha_id},
        cookies=cookies,
    )
    # Must be 403 Forbidden
    assert res.status_code == 403
    assert "not a member" in res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_role_enforcement_agent_cannot_modify_settings(client: AsyncClient, seeded_entities: dict):
    """
    Verifies RBAC:
    Support Agents are strictly blocked from mutating workspace settings.
    """
    # 1. Login as Support Agent in Alpha
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "agent@alpha.com", "password": "Password123!"},
    )
    assert login_res.status_code == 200
    cookies = login_res.cookies
    csrf_token = login_res.json()["csrf_token"]
    alpha_id = seeded_entities["ws_alpha"].id

    # 2. Attempt to update similarity threshold
    res = await client.patch(
        "/api/workspaces/current/settings",
        json={"similarity_threshold": 0.88},
        headers={"X-Workspace-Id": alpha_id, "X-CSRF-Token": csrf_token},
        cookies=cookies,
    )
    assert res.status_code == 403
    assert "required role" in res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_admin_can_update_settings_with_csrf(client: AsyncClient, seeded_entities: dict):
    """
    Verifies that an Admin can update settings when presenting a valid CSRF token.
    """
    # 1. Login as Admin in Alpha
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "admin@alpha.com", "password": "Password123!"},
    )
    assert login_res.status_code == 200
    cookies = login_res.cookies
    csrf_token = login_res.json()["csrf_token"]
    alpha_id = seeded_entities["ws_alpha"].id

    # 2. Update settings
    res = await client.patch(
        "/api/workspaces/current/settings",
        json={"similarity_threshold": 0.85, "proposal_expiry_hours": 48},
        headers={"X-Workspace-Id": alpha_id, "X-CSRF-Token": csrf_token},
        cookies=cookies,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["similarity_threshold"] == 0.85
    assert data["proposal_expiry_hours"] == 48

@pytest.mark.asyncio
async def test_csrf_protection_blocks_mutations(client: AsyncClient, seeded_entities: dict):
    """
    Verifies CSRF security:
    A POST/PATCH request with auth cookie but MISSING or INVALID CSRF header is rejected with 403.
    """
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "admin@alpha.com", "password": "Password123!"},
    )
    assert login_res.status_code == 200
    cookies = login_res.cookies
    alpha_id = seeded_entities["ws_alpha"].id

    # Request without X-CSRF-Token header
    res = await client.post(
        "/api/workspaces/current/members",
        json={"email": "charlie@alpha.com", "role": "support_agent", "full_name": "Charlie Agent"},
        headers={"X-Workspace-Id": alpha_id},
        cookies=cookies,
    )
    assert res.status_code == 403
    assert "csrf" in res.json()["detail"].lower()
