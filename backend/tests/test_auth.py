import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_admin_success(client: AsyncClient):
    """Verifies that an admin user can register and automatically receive their workspace & cookies."""
    payload = {
        "email": "newadmin@example.com",
        "password": "SecurePassword123!",
        "full_name": "New Admin",
        "workspace_name": "New Horizons",
    }
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["email"] == "newadmin@example.com"
    assert data["active_workspace"]["workspace_name"] == "New Horizons"
    assert data["active_workspace"]["role"] == "admin"
    assert "csrf_token" in data
    # Check cookies
    cookies = response.cookies
    assert "access_token" in cookies
    assert "csrf_token" in cookies

@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, seeded_entities: dict):
    """Verifies that registering with an existing email returns 400 Bad Request."""
    payload = {
        "email": "admin@alpha.com",
        "password": "Password123!",
        "full_name": "Duplicate Alice",
        "workspace_name": "Duplicate Corp",
    }
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, seeded_entities: dict):
    """Verifies successful login returns auth cookies and memberships."""
    payload = {
        "email": "admin@alpha.com",
        "password": "Password123!",
    }
    response = await client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "admin@alpha.com"
    assert data["active_workspace"]["role"] == "admin"
    assert "access_token" in response.cookies

@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, seeded_entities: dict):
    """Verifies that incorrect credentials return 401 Unauthorized."""
    payload = {
        "email": "admin@alpha.com",
        "password": "WrongPassword999!",
    }
    response = await client.post("/api/auth/login", json=payload)
    assert response.status_code == 401
    assert "incorrect email or password" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_get_me_authenticated(client: AsyncClient, seeded_entities: dict):
    """Verifies /api/auth/me returns the active session."""
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "agent@alpha.com", "password": "Password123!"},
    )
    assert login_res.status_code == 200
    cookies = login_res.cookies

    me_res = await client.get("/api/auth/me", cookies=cookies)
    assert me_res.status_code == 200
    data = me_res.json()
    assert data["user"]["email"] == "agent@alpha.com"
    assert data["active_workspace"]["role"] == "support_agent"

@pytest.mark.asyncio
async def test_logout(client: AsyncClient, seeded_entities: dict):
    """Verifies logout endpoint clears session cookies."""
    login_res = await client.post(
        "/api/auth/login",
        json={"email": "admin@alpha.com", "password": "Password123!"},
    )
    assert login_res.status_code == 200
    cookies = login_res.cookies

    logout_res = await client.post("/api/auth/logout", cookies=cookies)
    assert logout_res.status_code == 200
    assert logout_res.json()["message"] == "Logged out successfully."
