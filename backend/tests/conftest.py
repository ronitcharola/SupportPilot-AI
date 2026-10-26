import sys
from pathlib import Path
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Ensure backend directory is in python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, get_db
from app.main import app
from app.models.user import User, Customer
from app.models.workspace import Workspace, WorkspaceMembership, WorkspaceSettings
from app.services.auth_service import hash_password, create_access_token, generate_csrf_token

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Provides a clean in-memory database session for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    """Provides an AsyncClient bound to the FastAPI app with the test database."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()

@pytest_asyncio.fixture(scope="function")
async def client_factory(db_session: AsyncSession):
    """Creates isolated HTTP clients so several identities can hold separate cookie sessions."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    clients = []

    def _make_client() -> AsyncClient:
        transport = ASGITransport(app=app)
        ac = AsyncClient(transport=transport, base_url="http://test")
        clients.append(ac)
        return ac

    yield _make_client

    for ac in clients:
        await ac.aclose()
    app.dependency_overrides.clear()

@pytest_asyncio.fixture(scope="function")
async def seeded_entities(db_session: AsyncSession):
    """Creates two distinct workspaces, an admin, an agent, and an outside user for testing."""
    # Workspace 1: Alpha Corp
    ws_alpha = Workspace(id="ws-alpha-1111", name="Alpha Corp", slug="alpha-corp", is_active=True)
    db_session.add(ws_alpha)
    db_session.add(WorkspaceSettings(workspace_id=ws_alpha.id))

    # Workspace 2: Beta Corp
    ws_beta = Workspace(id="ws-beta-2222", name="Beta Corp", slug="beta-corp", is_active=True)
    db_session.add(ws_beta)
    db_session.add(WorkspaceSettings(workspace_id=ws_beta.id))

    # User 1: Admin in Alpha
    admin_alpha = User(
        id="usr-admin-1",
        email="admin@alpha.com",
        password_hash=hash_password("Password123!"),
        full_name="Alice Alpha",
        is_active=True,
    )
    db_session.add(admin_alpha)

    # User 2: Support Agent in Alpha
    agent_alpha = User(
        id="usr-agent-2",
        email="agent@alpha.com",
        password_hash=hash_password("Password123!"),
        full_name="Bob Alpha",
        is_active=True,
    )
    db_session.add(agent_alpha)

    # User 3: Admin in Beta (Strict outsider to Alpha)
    admin_beta = User(
        id="usr-admin-beta-3",
        email="admin@beta.com",
        password_hash=hash_password("Password123!"),
        full_name="Bella Beta",
        is_active=True,
    )
    db_session.add(admin_beta)

    await db_session.flush()

    # Memberships
    db_session.add(WorkspaceMembership(workspace_id=ws_alpha.id, user_id=admin_alpha.id, role="admin"))
    db_session.add(WorkspaceMembership(workspace_id=ws_alpha.id, user_id=agent_alpha.id, role="support_agent"))
    db_session.add(WorkspaceMembership(workspace_id=ws_beta.id, user_id=admin_beta.id, role="admin"))

    await db_session.commit()

    return {
        "ws_alpha": ws_alpha,
        "ws_beta": ws_beta,
        "admin_alpha": admin_alpha,
        "agent_alpha": agent_alpha,
        "admin_beta": admin_beta,
    }
