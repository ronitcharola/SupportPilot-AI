# SupportPilot AI — Multi-Tenant AI Customer Support SaaS with Human-in-the-Loop Safeguards

SupportPilot AI is an enterprise-grade customer support platform that blends autonomous RAG-powered customer interactions with strict **server-side Human-in-the-Loop (HITL) approval controls**.

---

## 🌟 Core Philosophy & Architecture

- **Human-in-the-Loop Guarantee**: AI agents can analyze, retrieve knowledge, draft responses, and propose operations (e.g. refunds, cancellations). However, **consequential actions cannot execute autonomously**; they are created as pending proposals and executed strictly after authenticated human approval under database row-level locking (`SELECT ... FOR UPDATE`).
- **Zero Mock Frontends**: Every UI interface connects to real, typed FastAPI backend endpoints.
- **Strict Multi-Tenant Isolation**: Every database table contains a non-nullable `workspace_id`. Queries are automatically scoped using the `WorkspaceContext` dependency and `scoped_query` repository helpers.

---

## ✅ Implemented Phases

| Phase | Status | Highlights |
| :--- | :--- | :--- |
| **1. Foundation** | Complete | Email/password auth with Argon2id, httpOnly JWT cookies, double-submit CSRF, workspaces, memberships, RBAC, tenant isolation. |
| **2. Ticket Management** | Complete | Customers, tickets, messages (incl. internal notes), assignment history, lifecycle-validated statuses, filters/sort/pagination, agent inbox, ticket detail, customer portal, demo seed. |
| **3. Knowledge Base + RAG** | Complete | Workspace-scoped document ingestion (TXT/MD/PDF, paste-text), Celery/ingestion pipeline, pgvector + SQLite vector store, retrieval previews, grounded chat with citations and human escalation, admin knowledge UI. 40 passing tests. |
| **4. AI Classification & Escalation** | Complete | Deterministic mock + strict-JSON LLM triage (category, priority, sentiment, intent, urgency), configurable escalation rules, grounded suggested reply drafts, AI triage card and escalated-only inbox filter. 53 passing tests. |
| 5. Human Approval (HITL) | Not started | — |
| 6. Analytics & Integrations | Not started | — |
| 7. Production Readiness | Not started | — |

See [HANDOFF.md](HANDOFF.md) for the precise status, known limitations and next steps.

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Frontend** | Next.js 14+ (App Router), TypeScript, Tailwind CSS, Lucide React, Recharts |
| **Backend** | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic, Celery, Redis |
| **Database** | PostgreSQL 16 + pgvector (with transparent local SQLite vector fallback) |
| **Security** | Argon2id password hashing, httpOnly SameSite JWT cookies, double-submit CSRF headers |
| **AI Subsystem** | Abstract Provider Layer (`MockProvider` for deterministic offline demo, OpenAI, Gemini), lexical mock embeddings, grounded RAG with citations |

---

## 🚀 Quickstart: Running with Docker Compose

Ensure Docker Desktop is running on your machine:

```bash
# Clone the repository and enter the directory
cd supportpilot

# Start all services (Frontend, Backend, Celery Worker, PostgreSQL+pgvector, Redis)
docker compose up --build
```

The backend container applies Alembic migrations and runs the idempotent seed script before serving traffic, so a fresh stack boots with demo data.

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API Docs (Swagger): [http://localhost:8000/docs](http://localhost:8000/docs)
- API Health Check: [http://localhost:8000/health](http://localhost:8000/health)

> Phase 3 note: the Celery worker runs `knowledge.ingest_document` (knowledge-base ingestion). `docker compose` sets `KNOWLEDGE_INGESTION_MODE=celery`; local development defaults to inline indexing so Redis is not required.

---

## 💻 Local Development Setup (Without Docker)

### 1. Backend Setup
```bash
cd backend

# Create and activate Python virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Apply database migrations
alembic upgrade head

# Seed initial demo workspaces, users, and settings
python scripts/seed.py

# Run FastAPI backend server
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup
```bash
cd frontend

# Install Node dependencies
npm install

# Run Next.js development server
npm run dev
# Running on http://localhost:3000
```

---

## 🎫 Ticket Management (Phase 2)

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `GET` | `/api/tickets` | List with `status`, `priority`, `category`, `assignee_id`, `unassigned`, `assigned_to_me`, `search`, `sort_by`, `sort_order`, pagination |
| `POST` | `/api/tickets` | Create a ticket (agent/admin) |
| `GET` | `/api/tickets/{id}` | Full thread with internal notes and `allowed_transitions` |
| `PATCH` | `/api/tickets/{id}` | Update status / priority / category |
| `GET`/`POST` | `/api/tickets/{id}/messages` | Read thread, add reply or internal note |
| `POST` | `/api/tickets/{id}/assign` | Assign to an admin/agent in the same workspace |
| `GET`/`POST` | `/api/portal/tickets` | Customer portal: list own tickets, submit a request |
| `GET` | `/api/portal/tickets/{id}` | Customer view; internal notes are always stripped server-side |
| `POST` | `/api/portal/tickets/{id}/messages` | Customer reply |

Rules enforced on the backend:
- Every ticket, message and assignment is workspace-scoped; cross-workspace ids return `404`.
- Status changes follow an explicit lifecycle (`open → in_progress → … → resolved/closed`) and illegal moves return `409`.
- Only admins/agents can change status, assign, or write internal notes; customers never receive internal notes.
- Priorities: `low`, `medium`, `high`, `urgent`. Categories: `billing`, `refunds`, `technical_issues`, `account_access`, `orders`, `shipping`, `product_questions`, `other`.

> The customer portal and AI chat are currently identified by email address only (no customer password/session). See ADR-007 in `docs/DECISIONS.md` and the limitations section of `HANDOFF.md`.

---

## 📚 Knowledge Base & Grounded RAG (Phase 3)

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `GET` | `/api/knowledge/documents` | List documents with `status`, `search`, sort and pagination |
| `POST` | `/api/knowledge/documents` | Upload `.txt`/`.md`/`.pdf` (admin) and index it |
| `POST` | `/api/knowledge/documents/text` | Add knowledge from pasted text (admin) |
| `GET` | `/api/knowledge/documents/{id}` | Document metadata; `include_chunks=true` for chunks |
| `POST` | `/api/knowledge/documents/{id}/reindex` | Re-chunk and re-embed (admin) |
| `DELETE` | `/api/knowledge/documents/{id}` | Delete document and its chunks (admin) |
| `POST` | `/api/knowledge/search` | Retrieval preview with scores, threshold and timing |
| `GET` | `/api/knowledge/stats` | Indexing health and embedding configuration |
| `POST` | `/api/ai/chat` | Grounded answer with citations, or human escalation |

Pipeline guarantees:
- Uploads are validated (type, size, encoding, empty/scanned PDFs) before a document is created.
- Documents are chunked (900 chars, 150 overlap), embedded in batches and indexed per workspace.
- Embeddings live in a pgvector column on PostgreSQL (HNSW cosine index) and as JSON on SQLite (Python cosine scoring).
- Every retrieval query filters by `workspace_id`; cross-tenant document ids return `404`.
- Chat answers only from retrieved chunks and cites them. If nothing clears the similarity threshold, the response is `escalated=true` with no invented answer.
- Knowledge writes are admin-only; support agents can read, preview retrieval and view stats.

Try it: sign in as `admin@acme.com` → **Knowledge Base**, then open [http://localhost:3000/portal/chat](http://localhost:3000/portal/chat?email=customer@acme.com) and ask “How long do refunds take?”. The five seeded Acme policies are already indexed.

---

## 🧠 AI Triage & Suggested Replies (Phase 4)

Every new ticket (staff or portal) is classified asynchronously through the provider layer and stored as advisory metadata:

- **Category, priority, sentiment, intent, confidence, summary and urgency score.**
- **Escalation flag** when urgency reaches the workspace's `auto_escalate_urgency_threshold`, the intent is sensitive (refund, chargeback, security, legal, account deletion, human handoff), sentiment is angry, confidence is below `AI_LOW_CONFIDENCE_THRESHOLD`, or the customer asks for a human.
- Triage **never changes ticket status, never sends messages, and never executes an action**. Applying the suggested category/priority is an explicit human click. Provider failures never block ticket intake.

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `POST` | `/api/tickets/{id}/classify` | Re-run triage; `?apply=true` applies the suggested category/priority |
| `POST` | `/api/tickets/{id}/suggested-reply` | Knowledge-grounded draft with citations; never saved or sent |
| `GET` | `/api/tickets?escalated=true` | Tickets flagged for human review |

In the UI, open any ticket to see the **AI Triage** card (intent, sentiment, urgency, confidence, reasons, Reclassify / Apply suggestion) and use **Draft with AI** in the composer to insert a cited draft for review. The inbox has an **Escalated only** filter.

> Customer portal responses deliberately hide all AI internals — customers only see customer-facing ticket data.

---

## 🧪 Running the Test Suite

```bash
cd backend
.venv\Scripts\activate
pytest -v
```

Current suite: **53 passing tests**. They validate:
- Admin registration, workspace provisioning, login/logout, session cookies
- Multi-tenant boundary isolation (Workspace Beta cannot read or mutate Workspace Alpha tickets)
- Role-Based Access Control (support agents blocked from workspace settings, unauthenticated callers blocked from ticket APIs)
- CSRF double-submit token verification on mutating requests
- Ticket CRUD, lifecycle/status-transition validation, enum + pagination validation
- Filters (status, priority, category, assignee, unassigned, search), sorting and pagination
- Internal-note redaction in the customer portal (list, detail and replies)
- Workspace-scoped ticket numbering and customer records
- Knowledge ingestion (text + file upload), chunking/embedding determinism, upload validation
- Knowledge RBAC (admin writes, agent reads, anonymous denial) and cross-workspace isolation
- Retrieval preview, reindex/delete chunk cleanup, document filters/sort/pagination
- Grounded chat citations, low-evidence escalation, unknown workspace handling
- Prompt-injection wrapper escaping and context formatting
- Ticket classification on creation, escalation thresholds/reasons, angry/human-request/low-confidence rules
- Reclassify and apply-suggestion endpoints, RBAC, cross-workspace denial, provider-failure resilience
- Grounded reply drafts with citations that are never persisted, and portal redaction of AI metadata

---

## 🔑 Pre-Seeded Demo Credentials

| Role | Workspace | Email | Password |
| :--- | :--- | :--- | :--- |
| **Admin** | Acme Corp Support (`acme-corp`) | `admin@acme.com` | `SupportPilot2026!` |
| **Support Agent** | Acme Corp Support (`acme-corp`) | `agent@acme.com` | `SupportPilot2026!` |
| **Admin (Isolation Test)** | Beta Industries (`beta-industries`) | `admin@beta.com` | `SupportPilot2026!` |

Customers use the separate portal at [http://localhost:3000/portal](http://localhost:3000/portal). Seeded customer emails: `customer@acme.com`, `priya@example.com`, `marcus@example.com`, `dana@northwind.io`.

---

## 📁 Repository Structure

```plaintext
supportpilot/
├── backend/                  # FastAPI REST API, Celery worker, AI orchestration
│   ├── app/
│   │   ├── ai/               # Providers, chunking, extraction, prompt defense, retriever
│   │   ├── api/v1/           # Modular REST routes (/auth, /workspaces, /tickets, /knowledge, /ai)
│   │   ├── models/           # SQLAlchemy 2.0 declarative models (incl. portable VectorType)
│   │   ├── schemas/          # Pydantic v2 validation models
│   │   ├── services/         # Domain logic: RAG, chat, ticket triage, grounded reply drafts, auth
│   │   ├── tasks/            # Celery app + knowledge ingestion task
│   │   ├── database.py       # Async SQLAlchemy engine & session factory
│   │   └── dependencies.py   # WorkspaceContext, RBAC guards, CSRF verifier
│   ├── alembic/              # Database migration versions
│   ├── scripts/seed.py       # Idempotent demo data + knowledge seeder
│   └── tests/                # Automated pytest suite
├── frontend/                 # Next.js App Router, Tailwind CSS, typed API client
│   ├── src/app/              # Pages & layouts (dashboard, tickets, knowledge, portal, chat)
│   ├── src/components/       # Toast provider and shared UI
│   ├── src/contexts/         # AuthContext & Session management
│   └── src/lib/api.ts        # Typed API client
├── docs/                     # Architectural decisions & metric definitions
│   └── DECISIONS.md
├── docker-compose.yml        # Production multi-container composition
└── AGENTS.md                 # Agent operating guidelines & security constraints
```
#   S u p p o r t P i l o t - A I  
 