# Architectural Decision Records (ADRs)

## ADR-001: Multi-Tenant Workspace Scoping
- **Status**: Accepted
- **Context**: SupportPilot AI serves multiple enterprise clients (workspaces). Strict multi-tenancy is critical to prevent cross-customer data leakage.
- **Decision**: Every operational record (`tickets`, `ticket_messages`, `knowledge_documents`, `document_chunks`, `action_proposals`, `audit_logs`) has a non-nullable `workspace_id` foreign key. A FastAPI dependency `get_workspace_context` extracts the active workspace from the user's authenticated session or `X-Workspace-Id` header, verifies membership in `workspace_memberships`, and provides a `WorkspaceContext` object. A repository helper `scoped_query(db, Model, ctx)` is used to construct queries with guaranteed workspace scoping.

## ADR-002: Dual Database Dialect Support (PostgreSQL+pgvector & SQLite Local Fallback)
- **Status**: Accepted
- **Context**: The production stack specifies PostgreSQL 16 + pgvector. However, local developer machines (such as Windows environments lacking Docker Desktop or local PostgreSQL services) must still be able to run tests, migrations, and development workflows seamlessly.
- **Decision**: In `docker-compose.yml`, PostgreSQL 16 + pgvector is the containerized database. In `backend/app/models/vector.py`, a `VectorType` column uses native `pgvector.sqlalchemy.Vector` on PostgreSQL and JSON text on SQLite. If `DATABASE_URL` is SQLite (`sqlite+aiosqlite:///...`), vector similarity is computed in Python (`app/ai/retriever.py`); on PostgreSQL, retrieval orders by the `<=>` cosine-distance operator and the migration creates an HNSW cosine index.

## ADR-003: Auth and Session Security
- **Status**: Accepted
- **Context**: Secure authentication is required for Admins, Support Agents, and Customers.
- **Decision**:
  - Passwords hashed using Argon2id (`passlib[argon2]`).
  - Access tokens generated as signed JWTs stored in `httpOnly`, `SameSite=Lax`, and `Secure` (in HTTPS) cookies.
  - State-modifying requests (`POST`, `PUT`, `PATCH`, `DELETE`) require a valid `X-CSRF-Token` header matching the issued CSRF cookie.
  - Role-based authorization is enforced exclusively on the backend via dependency injection (`require_role(["admin"])`, `require_role(["admin", "support_agent"])`).

## ADR-004: Consequential Action Decoupling (HITL Guarantee)
- **Status**: Accepted
- **Context**: AI should not be capable of autonomously executing financial or account-altering actions.
- **Decision**:
  - The AI Tool layer distinguishes between Read-Only Tools (e.g. `search_knowledge_base`, `get_ticket_details`) and Consequential Tools (e.g. `propose_refund`, `propose_order_cancellation`).
  - Consequential tool calls only create an `action_proposals` record with status `pending`.
  - The AI execution engine does NOT possess client credentials or methods to trigger execution APIs.
  - Execution occurs strictly in `ApprovalService.approve_proposal()` under row-level locking (`SELECT ... FOR UPDATE`), requiring an authenticated Agent or Admin session.

## ADR-005: AI Provider Abstraction
- **Status**: Accepted
- **Context**: The platform must run completely offline without requiring paid API keys, while supporting production OpenAI and Google Gemini models.
- **Decision**: Implement `LLMProvider` and `EmbeddingProvider` abstract protocols. Provide `MockProvider` (deterministic responses and synthetic embeddings) as the default in `DEMO_MODE=true` and during automated tests, alongside `OpenAIProvider` and `GeminiProvider`.

## ADR-006: Explicit Ticket Status Lifecycle
- **Status**: Accepted (Phase 2)
- **Context**: Free-form status updates let an agent (or a future AI tool) move a ticket into states that skip required review — for example jumping a `pending_approval` ticket straight back to `open`, or silently reopening a closed ticket.
- **Decision**: The allowed transitions live in `app/services/ticket_service.py` (`STATUS_TRANSITIONS`) and are validated on every PATCH. Illegal moves return `409 Conflict` with the list of legal next states. The same list is returned as `allowed_transitions` on every ticket payload so the UI only offers server-approved options. Self-transitions are treated as no-ops.
- **Lifecycle**:
  - `open` → `in_progress`, `pending_approval`, `waiting_for_customer`, `escalated`, `resolved`, `closed`
  - `in_progress` → `open`, `pending_approval`, `waiting_for_customer`, `escalated`, `resolved`, `closed`
  - `pending_approval` / `waiting_for_customer` / `escalated` → `in_progress`, `escalated` (where applicable), `resolved`, `closed`
  - `resolved` → `open`, `closed`
  - `closed` → `open`
- **Consequences**: A reopen must pass through `open`; tickets cannot rot in `pending_approval`. Conversation side-effects are also deterministic: a public agent reply moves an active ticket to `waiting_for_customer`, a customer reply moves it to `in_progress` (or reopens a resolved/closed ticket).

## ADR-007: Customer Portal Identity (email-scoped demo session)
- **Status**: Accepted, with known limitation (Phase 2)
- **Context**: Phase 1 introduced `Customer` records separate from staff `User`/`WorkspaceMembership` accounts, but no customer authentication. Phase 2 needs a working portal (create/list/reply) and provable internal-note isolation without expanding the auth model mid-phase.
- **Decision**: Portal endpoints resolve the caller's identity from a `email` query parameter plus `workspace_slug`, and return `404` when the email does not own the ticket. Internal notes are filtered server-side in every portal response, and portal replies can never set `is_internal_note`.
- **Consequences / risk**: Tenant scoping and note redaction are enforced, but a caller who knows another customer's email could read that customer's tickets. This is acceptable only for the demo build. **Before production, customer identity must be authenticated** (invite/magic-link or password + session cookie); the portal endpoints should then resolve the customer from the session and ignore client-supplied emails. Tracked in `HANDOFF.md` and planned for the Phase 7 hardening pass.

## ADR-008: UI Toolkit Deviation (Tailwind-first components)
- **Status**: Accepted (Phase 1/2)
- **Context**: The target stack names `shadcn/ui` and Recharts. Phases 1–2 built the dashboard with hand-rolled Tailwind components (plus Lucide icons) because no component-library scaffolding existed yet and none of the Phase 1–2 screens required charts.
- **Decision**: Keep the current Tailwind-first component style rather than re-platforming the existing working UI. Add a small, accessible in-house toast provider instead of pulling in a notification dependency. Recharts will be introduced when the analytics screens are built in Phase 6; `shadcn/ui` adoption is deferred and can be revisited if the design system needs it.
- **Consequences**: No visual regression risk in this phase, no extra dependencies. Components are less standardized than a shadcn-based system, so future contributors should reuse `src/components/*` and the existing `glass-card` styles.

## ADR-009: Container Bootstrap (migrations + seed)
- **Status**: Accepted (Phase 2)
- **Context**: The FastAPI lifespan calls `Base.metadata.create_all`, which creates tables but neither tracks Alembic revisions nor seeds demo data. A fresh `docker compose up --build` therefore produced an empty, unversioned database.
- **Decision**: The compose `backend` service runs `alembic upgrade head && python scripts/seed.py` before starting uvicorn. The seed script is idempotent. The frontend ships a multi-stage-free `node:20-alpine` Dockerfile with `NEXT_PUBLIC_API_URL` injected at build time. A Celery app (`app/tasks/celery_app.py`) declares the Phase 3 ingestion task via `include`.
- **Consequences**: Fresh stacks boot with demo data and a correct `alembic_version`; local (`uvicorn`) development still relies on the documented manual `alembic upgrade head` + seed steps.

## ADR-010: Portable Embedding Column & Fixed Dimension
- **Status**: Accepted (Phase 3)
- **Context**: Knowledge chunks need vector storage on PostgreSQL and a working local fallback on SQLite. Changing embedding models later must not silently corrupt retrieval.
- **Decision**:
  - `app/models/vector.py` defines `VectorType`, which renders as `vector(1536)` on PostgreSQL and `TEXT` (JSON array) on SQLite. `app/ai/retriever.py` uses the `<=>` distance operator with an HNSW cosine index on PostgreSQL, and Python cosine similarity on SQLite.
  - The embedding dimension is fixed by `EMBEDDING_DIMENSION` (and the physical column). Each document records the provider, model and dimension used, and retrieval only considers chunks whose document dimension matches the current query embedding dimension.
  - Switching providers/dimensions requires reindexing; until then those chunks are ignored instead of producing meaningless scores.
- **Consequences**: One codebase runs on both databases. On SQLite, retrieval scans at most `RETRIEVAL_SCAN_LIMIT` chunks for the workspace and scores them in Python — acceptable for a demo corpus, not for large production corpora (PostgreSQL uses the index).

## ADR-011: Ingestion Execution Model (inline default, Celery in containers)
- **Status**: Accepted (Phase 3)
- **Context**: Uploads must be chunked and embedded. A Celery worker exists, but local development and automated tests often run without Redis, and an upload that silently stays `pending` forever is worse than a slower request.
- **Decision**:
  - `KNOWLEDGE_INGESTION_MODE=inline` (default) runs chunking/embedding inside the request through the same service used by the worker.
  - `KNOWLEDGE_INGESTION_MODE=celery` queues `knowledge.ingest_document`; if publishing to the broker fails, the API logs a warning and falls back to inline indexing instead of leaving the document pending.
  - Ingestion failures are persisted on the document (`status=failed`, `error_message`) rather than returned as opaque 500s. The Celery task retries transient crashes up to 3 times; permanent content errors are not retried.
  - Only extracted text is stored in the database (`source_text`), so reindexing is idempotent and independent of local disk state.
- **Consequences**: `docker compose` exercises the real worker path; tests and local `uvicorn` work without Redis. Large documents block the upload request in inline mode (bounded by `MAX_UPLOAD_BYTES`).

## ADR-012: Grounded Answers, Citations and Low-Evidence Escalation
- **Status**: Accepted (Phase 3)
- **Context**: The product promise is that AI answers are grounded in workspace knowledge and hand off to humans when it cannot answer.
- **Decision**:
  - `POST /api/ai/chat` embeds the question, retrieves workspace-scoped chunks above the similarity threshold, and asks the LLM to answer **only** from numbered context blocks, citing `[n]`.
  - Responses include citations (document, chunk, excerpt, score), the threshold used and the top score. If no chunk clears the threshold, or the provider returns no usable answer, the response is `escalated=true` with no citations and a handoff message. Nothing is guessed.
  - Retrieved context and the customer question are wrapped in `<customer_input>` tags and stripped of tag-shaped injection attempts (`app/ai/prompt_defense.py`). Retrieved text is treated strictly as data.
  - The chat endpoint is read-only: it cannot create tickets, change ticket state or execute consequential actions.
  - Because mock embeddings are lexical, they use a separately calibrated `MOCK_SIMILARITY_THRESHOLD` (default `0.12`); real providers use the workspace's `similarity_threshold` (default `0.72`).
- **Consequences**: Offline demos produce extractive, cited answers and escalate unrelated questions. The mock LLM never fabricates text, but it is not a semantic model, so answer phrasing is basic by design. The chat endpoint is public like the portal and currently has no rate limiting (tracked in `HANDOFF.md`).

## ADR-013: Knowledge Base Authorization
- **Status**: Accepted (Phase 3)
- **Context**: Workspace knowledge influences every AI answer, so who can change it matters as much as who can read tickets.
- **Decision**:
  - Admins own the corpus: upload, paste-text, reindex and delete.
  - Support agents (and admins) can list documents, view chunks, run retrieval previews and read stats.
  - Every document/chunk query filters by `workspace_id` in SQL, and `KnowledgeRetriever` requires a non-empty `workspace_id` and applies it to both `document_chunks` and its parent `knowledge_documents` table. Cross-workspace document ids return `404`.
  - Portal chat resolves the workspace from its public slug and only ever retrieves that workspace's indexed chunks.
- **Consequences**: Agents cannot poison the corpus; customers can benefit from it without direct access to document management.
