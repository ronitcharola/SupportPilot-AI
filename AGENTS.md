# AGENTS.md — SupportPilot AI Operating Guidelines

This document establishes the architecture conventions, run commands, security rules, and development practices for the SupportPilot AI codebase.

---

## 1. Project Overview & Philosophy
SupportPilot AI is a multi-tenant AI customer-support SaaS platform featuring a **human-in-the-loop (HITL) approval system**.
- **Core Principle**: AI models may classify, retrieve, draft, and propose, but consequential actions (refunds, order cancellations, account mutations) execute **only after server-side authenticated human approval**.
- **No Mock Frontends**: Every screen connects to real, typed backend endpoints.
- **Tenant Isolation**: Every operational query MUST be workspace-scoped. Unscoped queries are strictly prevented.

---

## 2. Technology Stack & Directory Structure
- **Frontend**: Next.js 14+ (App Router), TypeScript, Tailwind CSS, Lucide React, Recharts.
- **Backend**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic, Celery, Redis.
- **Database**: PostgreSQL 16 with pgvector extension (with SQLite local-fallback capability for environments without Docker/Postgres).
- **Environment & Infra**: Docker, Docker Compose, `.env` file configuration.

```
supportpilot/
├── backend/          # FastAPI REST API, Celery worker, AI orchestration
│   ├── app/
│   │   ├── ai/       # LLM/Embedding providers, tools, RAG, prompt defense
│   │   ├── api/      # REST API v1 endpoints
│   │   ├── models/   # SQLAlchemy 2.x declarative models
│   │   ├── schemas/  # Pydantic v2 validation models
│   │   ├── services/ # Domain business logic & policy engine
│   │   └── tasks/    # Celery async tasks
│   └── tests/        # Pytest test suite
├── frontend/         # Next.js App Router, Tailwind CSS, typed API client
├── docs/             # DECISIONS.md, METRICS.md, API.md
└── docker-compose.yml
```

---

## 3. Key Run & Test Commands

### Running with Docker Compose (Production / Full Stack)
```bash
docker compose up --build
```

### Running Backend Locally (Development)
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --port 8000
```

### Running Backend Tests
```bash
cd backend
pytest -v
```

### Running Frontend Locally (Development)
```bash
cd frontend
npm install
npm run dev
# Running on http://localhost:3000
```

---

## 4. Multi-Tenant Security Rules
1. **Workspace Context**: Every protected endpoint requires the `WorkspaceContext` FastAPI dependency.
2. **Scoped Queries**: Use the `scoped_query(db, Model, ctx)` helper or explicitly include `.where(Model.workspace_id == ctx.workspace_id)`.
3. **Role-Based Access Control (RBAC)**:
   - `Admin`: Full workspace management, settings, integrations, analytics, audit logs.
   - `Support Agent`: Ticket management, review proposals, approve/reject actions, reply.
   - `Customer`: View only own submitted tickets and messages.
4. **Untrusted Input Protection**:
   - Customer messages and uploaded documents must be wrapped in `<customer_input>` tags.
   - Strict Pydantic parsing of AI output prevents arbitrary tool execution.
5. **Human Approval Server-Side Guarantee**:
   - The AI/tool layer has NO code path to execute consequential actions.
   - Consequential tools ONLY create `action_proposals` in `pending` status.
   - Approval endpoint enforces row-level locking (`SELECT FOR UPDATE`), verifies idempotency, and re-validates permissions before execution.

---

## 5. Architectural Conventions
- **Pydantic Schemas**: Separate request schemas, response schemas, and internal schemas.
- **Error Handling**: Return clean RFC 7807 compatible or consistent JSON error shapes (`{"detail": "..."}`). Never leak stack traces.
- **Provider Abstraction**: All LLM and Embedding interactions go through `LLMProvider` and `EmbeddingProvider` protocols (`MockProvider`, `OpenAIProvider`, `GeminiProvider`). The app must always run out of the box with `MockProvider`.
- **Audit Trails**: All approvals, rejections, executions, and auth events are written to the immutable `audit_logs` table.
